#!/usr/bin/env python3
"""Build an artificial Confluence space with blind text for import/export tests.

Creates a space (or fills an existing one), a skewed page hierarchy built by
preferential attachment (like real grown spaces), a skewed version
distribution (a few "hot" pages with 30-50 versions, many with only a
handful) and dummy attachments, optionally with a data-volume target.

All structure is deterministic for a given --seed. Long runs are resumable:
progress is checkpointed to ~/.cache/confluence-markdown/build_state_<KEY>.json
after every page and every few versions; a re-run continues exactly where the
previous one stopped (--fresh discards the state).
"""

import argparse
import contextlib
import io
import json
import random
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from confluence_markdown.client import ConfluenceClient  # noqa: E402
from confluence_markdown.config import ConfigManager  # noqa: E402

LOREM_WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua enim ad minim veniam "
    "quis nostrud exercitation ullamco laboris nisi aliquip ex ea commodo "
    "consequat duis aute irure in reprehenderit voluptate velit esse cillum "
    "eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident "
    "sunt culpa qui officia deserunt mollit anim id est laborum"
).split()

CHAPTER_THEMES = [
    "Organisation und Prozesse",
    "Technische Dokumentation",
    "Projekte und Planung",
    "Betrieb und Wartung",
    "Richtlinien und Vorlagen",
    "Archiv und Altbestand",
    "Besprechungen und Protokolle",
    "Schulung und Onboarding",
    "Schnittstellen und Systeme",
    "Qualität und Tests",
]

MAX_DEPTH = 5
MAX_CHILDREN = 30

# Smallest valid 1x1 transparent PNG
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049"
    "454e44ae426082"
)


def sentence(rng: random.Random) -> str:
    words = rng.choices(LOREM_WORDS, k=rng.randint(6, 14))
    return " ".join(words).capitalize() + "."


def paragraph(rng: random.Random) -> str:
    return " ".join(sentence(rng) for _ in range(rng.randint(3, 6)))


def title_words(rng: random.Random, k: int = 3) -> str:
    return " ".join(w.capitalize() for w in rng.sample(LOREM_WORDS, k))


def page_markdown(rng: random.Random, title: str, version: int) -> str:
    """Markdown body; varies with version so real diffs exist."""
    parts = [f"# {title}", "", f"*Testinhalt, Stand Version {version}.*", ""]
    for _ in range(rng.randint(2, 4)):
        parts += [f"## {title_words(rng)}", "", paragraph(rng), ""]
    parts += ["### Punkte", ""]
    parts += [f"- {sentence(rng)}" for _ in range(rng.randint(3, 6))]
    parts += ["", "| Merkmal | Wert | Status |", "|---|---|---|"]
    for _ in range(rng.randint(2, 5)):
        parts.append(
            f"| {title_words(rng, 1)} | {rng.randint(1, 999)} "
            f"| {rng.choice(['offen', 'aktiv', 'erledigt'])} |"
        )
    parts += ["", "```", f"beispiel_wert = {rng.randint(1000, 9999)}", "```", ""]
    return "\n".join(parts)


def build_tree(rng: random.Random, total_pages: int, n_chapters: int) -> list:
    """Grow a hierarchy by preferential attachment.

    Returns a list of nodes (title, parent_index or None for the space
    homepage). Well-connected nodes attract more children, giving the
    skewed, organically grown shape of real spaces.
    """
    nodes = []
    depth = []
    children = []
    numbering = []  # hierarchical label per node, e.g. "3.2.1"

    n_chapters = min(n_chapters, len(CHAPTER_THEMES), max(1, total_pages))
    for i in range(n_chapters):
        nodes.append((f"Kapitel {i + 1}: {CHAPTER_THEMES[i]}", None))
        depth.append(1)
        children.append(0)
        numbering.append(str(i + 1))

    while len(nodes) < total_pages:
        eligible = [
            i for i in range(len(nodes))
            if depth[i] < MAX_DEPTH and children[i] < MAX_CHILDREN
        ]
        weights = [children[i] + 1 for i in eligible]
        parent = rng.choices(eligible, weights=weights, k=1)[0]
        children[parent] += 1
        label = f"{numbering[parent]}.{children[parent]}"
        nodes.append((f"{label} {title_words(rng)}", parent))
        depth.append(depth[parent] + 1)
        children.append(0)
        numbering.append(label)

    return nodes


def version_targets(rng: random.Random, n_pages: int, total_versions: int) -> list:
    """Skewed per-page version counts, scaled to roughly total_versions."""
    targets = []
    n_hot = max(1, n_pages // 10)
    n_medium = max(1, n_pages * 3 // 10)
    for i in range(n_pages):
        if i < n_hot:
            targets.append(rng.randint(30, 50))
        elif i < n_hot + n_medium:
            targets.append(rng.randint(10, 20))
        else:
            targets.append(rng.randint(2, 5))
    rng.shuffle(targets)
    scale = total_versions / sum(targets)
    return [max(1, round(t * scale)) for t in targets]


def plan_attachments(rng: random.Random, count: int, total_mb: float,
                     n_nodes: int) -> list:
    """Deterministic attachment plan: (node_index, kind, size, second_version).

    kind: 0=txt, 1=csv, 2=png, 3=large binary. About 10% become large
    binaries whose sizes are scaled to fill the total_mb budget.
    """
    plan = []
    n_large = max(1, count // 10) if total_mb > 0 else 0
    large_slots = set(rng.sample(range(count), n_large)) if n_large else set()
    raw_sizes = {i: rng.uniform(0.5, 5.0) for i in large_slots}
    scale = (total_mb / sum(raw_sizes.values())) if raw_sizes else 0
    for n in range(count):
        node = rng.randrange(n_nodes)
        second = rng.random() < 0.3
        if n in large_slots:
            size = max(64 * 1024, int(raw_sizes[n] * scale * 1024 * 1024))
            plan.append((node, 3, size, False))
        else:
            plan.append((node, n % 3, 0, second))
    return plan


def find_page(client: ConfluenceClient, space_key: str, title: str):
    resp = client._request(
        "GET",
        f"{client.api_base}/content",
        params={"spaceKey": space_key, "title": title, "limit": 1},
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def space_exists(client: ConfluenceClient, key: str) -> bool:
    resp = client._request("GET", f"{client.api_base}/space/{key}")
    return resp.status_code == 200


def create_space(client: ConfluenceClient, key: str, name: str) -> bool:
    payload = {
        "key": key,
        "name": name,
        "description": {
            "plain": {
                "value": "Künstlicher Bereich für Import-Export-Tests (Blindtext).",
                "representation": "plain",
            }
        },
    }
    resp = client._request("POST", f"{client.api_base}/space", json=payload)
    if resp.status_code in (200, 201):
        return True
    print(f"FEHLER: Bereich konnte nicht angelegt werden (HTTP {resp.status_code}).")
    print(resp.text[:500])
    print(
        f"\nBitte den Bereich '{key}' manuell in der Confluence-UI anlegen und "
        "das Skript mit --skip-space-create erneut starten."
    )
    return False


def get_homepage_id(client: ConfluenceClient, key: str) -> str:
    resp = client._request(
        "GET", f"{client.api_base}/space/{key}", params={"expand": "homepage"}
    )
    resp.raise_for_status()
    return resp.json()["homepage"]["id"]


def update_page(client: ConfluenceClient, page_id: str, title: str,
                version: int, markdown: str) -> None:
    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "version": {"number": version},
        "body": {
            "storage": {
                "value": client._markdown_to_html(markdown),
                "representation": "storage",
            }
        },
    }
    resp = client._request(
        "PUT", f"{client.api_base}/content/{page_id}", json=payload
    )
    resp.raise_for_status()


def make_attachment_file(rng: random.Random, directory: Path, n: int,
                         kind: int, size: int) -> Path:
    if kind == 0:
        path = directory / f"dokument_{n:04d}.txt"
        path.write_text(paragraph(rng) + "\n", encoding="utf-8")
    elif kind == 1:
        path = directory / f"daten_{n:04d}.csv"
        rows = ["id;name;wert"]
        rows += [
            f"{i};{title_words(rng, 1)};{rng.randint(1, 999)}" for i in range(10)
        ]
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    elif kind == 2:
        path = directory / f"bild_{n:04d}.png"
        path.write_bytes(PNG_BYTES)
    else:
        path = directory / f"unterlage_{n:04d}.bin"
        path.write_bytes(rng.randbytes(size))
    return path


class BuildState:
    """Checkpoint file so multi-hour runs can resume exactly where they stopped."""

    def __init__(self, space_key: str, fresh: bool):
        cache_dir = Path.home() / ".cache" / "confluence-markdown"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.path = cache_dir / f"build_state_{space_key}.json"
        self.data = {"pages": {}, "attachments_done": 0}
        if self.path.exists() and not fresh:
            self.data = json.loads(self.path.read_text())

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data))

    def page(self, idx: int) -> dict:
        return self.data["pages"].get(str(idx), {})

    def set_page(self, idx: int, page_id: str, versions_done: int) -> None:
        self.data["pages"][str(idx)] = {
            "id": page_id, "versions_done": versions_done,
        }


class Progress:
    def __init__(self, total_writes: int, quiet: bool):
        self.total = total_writes
        self.done = 0
        self.start = time.monotonic()
        self.quiet = quiet

    def tick(self, n: int = 1) -> None:
        self.done += n

    def eta(self) -> str:
        rate = self.done / max(1e-6, time.monotonic() - self.start)
        remaining = (self.total - self.done) / max(0.1, rate)
        return f"{int(remaining // 3600)}h{int(remaining % 3600 // 60):02d}m"

    def line(self, prefix: str) -> None:
        if not self.quiet:
            print(
                f"{prefix} — Requests {self.done}/{self.total}, ETA {self.eta()}",
                flush=True,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Künstlichen Confluence-Testbereich mit Blindtext aufbauen"
    )
    parser.add_argument("--space-key", default="IETEST")
    parser.add_argument("--space-name", default="Import-Export-Test")
    parser.add_argument("--pages", type=int, default=50)
    parser.add_argument("--versions", type=int, default=600)
    parser.add_argument("--attachments", type=int, default=50)
    parser.add_argument("--attachment-mb", type=float, default=0,
                        help="Zielvolumen aller Anhänge in MB (0 = nur Mini-Dateien)")
    parser.add_argument("--chapters", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", default="default")
    parser.add_argument("--skip-space-create", action="store_true",
                        help="Bereich existiert schon (z. B. manuell angelegt)")
    parser.add_argument("--fresh", action="store_true",
                        help="Checkpoint-Zustand verwerfen und neu beginnen")
    parser.add_argument("--sleep", type=float, default=0.05,
                        help="Pause zwischen Schreib-Requests in Sekunden")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--quiet", "-q", action="store_true")
    args = parser.parse_args()

    config = ConfigManager().load_config(args.profile)
    if not config:
        print(f"FEHLER: Profil '{args.profile}' nicht gefunden.")
        return 1
    client = ConfluenceClient(
        base_url=config["base_url"],
        username=config.get("username"),
        password=config.get("password"),
        token=config.get("token"),
        verbose=args.verbose,
        cache_enabled=False,
    )

    # client.create_page/upload_attachment print several lines per call;
    # at thousands of writes that noise hides the progress lines.
    def silence():
        return (
            contextlib.redirect_stdout(io.StringIO())
            if args.quiet or args.pages > 20
            else contextlib.nullcontext()
        )

    rng = random.Random(args.seed)
    state = BuildState(args.space_key, args.fresh)

    if not args.skip_space_create and not space_exists(client, args.space_key):
        if not create_space(client, args.space_key, args.space_name):
            return 1
        print(f"Bereich {args.space_key} angelegt.")

    homepage_id = get_homepage_id(client, args.space_key)
    if not args.quiet:
        print(f"Startseite: {homepage_id}")

    nodes = build_tree(rng, args.pages, args.chapters)
    targets = version_targets(rng, len(nodes), args.versions)
    att_plan = plan_attachments(
        rng, args.attachments, args.attachment_mb, len(nodes)
    )

    total_writes = len(nodes) + sum(t - 1 for t in targets) + len(att_plan)
    # progress lines are wanted even with --quiet
    progress = Progress(total_writes, quiet=False)

    page_ids: list = []
    created_pages = 0
    created_versions = 0
    for idx, (title, parent_idx) in enumerate(nodes):
        parent_id = homepage_id if parent_idx is None else page_ids[parent_idx]
        saved = state.page(idx)
        page_id = saved.get("id")
        versions_done = saved.get("versions_done", 0)

        # page_markdown consumes rng draws: always generate all versions so
        # the stream stays aligned on resume, upload only the missing ones.
        bodies = [
            page_markdown(rng, title, v) for v in range(1, targets[idx] + 1)
        ]

        if page_id is None:
            page_id = find_page(client, args.space_key, title)
            if page_id:
                versions_done = targets[idx]  # pre-state page: leave as is
        if page_id is None:
            with silence():
                page = client.create_page(
                    args.space_key, title, bodies[0], parent_id
                )
            page_id = page["id"]
            versions_done = 1
            created_pages += 1
            created_versions += 1
            progress.tick()
            time.sleep(args.sleep)
        page_ids.append(page_id)

        for version in range(versions_done + 1, targets[idx] + 1):
            update_page(client, page_id, title, version, bodies[version - 1])
            versions_done = version
            created_versions += 1
            progress.tick()
            time.sleep(args.sleep)
            if version % 20 == 0:
                state.set_page(idx, page_id, versions_done)
                state.save()

        state.set_page(idx, page_id, versions_done)
        state.save()
        if (idx + 1) % 25 == 0 or idx + 1 == len(nodes):
            progress.line(f"Seiten {idx + 1}/{len(nodes)}")

    created_attachments = 0
    uploaded_bytes = 0
    start_att = state.data.get("attachments_done", 0)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for n, (node_idx, kind, size, second) in enumerate(att_plan):
            # keep rng draws aligned: regenerate file even when skipping
            path = make_attachment_file(rng, tmp_dir, n, kind, size)
            second_body = paragraph(rng) + "\n" if second else None
            if n < start_att:
                path.unlink()
                continue
            with silence():
                client.upload_attachment(
                    str(page_ids[node_idx]), str(path), "Testdaten v1"
                )
            created_attachments += 1
            uploaded_bytes += path.stat().st_size
            progress.tick()
            if second_body and kind in (0, 1):
                path.write_text(second_body, encoding="utf-8")
                with silence():
                    client.upload_attachment(
                        str(page_ids[node_idx]), str(path), "Testdaten v2"
                    )
                uploaded_bytes += path.stat().st_size
            path.unlink()
            state.data["attachments_done"] = n + 1
            if (n + 1) % 20 == 0:
                state.save()
            time.sleep(args.sleep)
            if (n + 1) % 100 == 0 or n + 1 == len(att_plan):
                progress.line(
                    f"Anhänge {n + 1}/{len(att_plan)} "
                    f"({uploaded_bytes / 1024 / 1024:.0f} MB)"
                )
    state.save()

    print("\nFertig:")
    print(f"  Seiten neu angelegt: {created_pages} (von {len(nodes)} geplant)")
    print(f"  Seitenversionen erzeugt: {created_versions}")
    print(f"  Anhänge hochgeladen: {created_attachments}")
    print(f"  Anhang-Volumen: {uploaded_bytes / 1024 / 1024:.1f} MB")
    print(f"  Bereich: {client.base_url}/display/{args.space_key}")
    print(f"  Checkpoint: {state.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
