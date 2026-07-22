#!/usr/bin/env python3
"""Build an artificial Confluence space with blind text for import/export tests.

Creates a space (or fills an existing one), a three-level page hierarchy,
a skewed version distribution similar to the most complex real spaces
(a few "hot" pages with 30-50 versions, many with only a handful), and
dummy attachments with attachment versions.

All content is deterministic for a given --seed, so re-runs produce the
same structure; already existing pages (matched by title) are skipped.
"""

import argparse
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
]

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


def build_tree(rng: random.Random, total_pages: int) -> list:
    """Return list of nodes: (title, parent_index or None for homepage)."""
    nodes = []
    n_chapters = min(len(CHAPTER_THEMES), max(1, total_pages // 8))
    for i, theme in enumerate(CHAPTER_THEMES[:n_chapters], start=1):
        nodes.append((f"Kapitel {i}: {theme}", None))
    remaining = total_pages - n_chapters
    chapter_indices = list(range(n_chapters))
    sub_count = 0
    while remaining > 0:
        chapter = chapter_indices[sub_count % n_chapters]
        chapter_no = chapter + 1
        sub_no = sub_count // n_chapters + 1
        sub_title = f"{chapter_no}.{sub_no} {title_words(rng)}"
        nodes.append((sub_title, chapter))
        sub_index = len(nodes) - 1
        remaining -= 1
        sub_count += 1
        # every third subpage gets a depth-3 child if budget allows
        if remaining > 0 and sub_count % 3 == 0:
            child_title = f"{chapter_no}.{sub_no}.1 {title_words(rng)}"
            nodes.append((child_title, sub_index))
            remaining -= 1
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


def find_page(client: ConfluenceClient, space_key: str, title: str):
    resp = client._request(
        "GET",
        f"{client.api_base}/content",
        params={"spaceKey": space_key, "title": title, "limit": 1},
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


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


def make_attachment_file(rng: random.Random, directory: Path, n: int) -> Path:
    kind = n % 3
    if kind == 0:
        path = directory / f"dokument_{n:02d}.txt"
        path.write_text(paragraph(rng) + "\n", encoding="utf-8")
    elif kind == 1:
        path = directory / f"daten_{n:02d}.csv"
        rows = ["id;name;wert"]
        rows += [
            f"{i};{title_words(rng, 1)};{rng.randint(1, 999)}" for i in range(10)
        ]
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    else:
        path = directory / f"bild_{n:02d}.png"
        path.write_bytes(PNG_BYTES)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Künstlichen Confluence-Testbereich mit Blindtext aufbauen"
    )
    parser.add_argument("--space-key", default="IETEST")
    parser.add_argument("--space-name", default="Import-Export-Test")
    parser.add_argument("--pages", type=int, default=50)
    parser.add_argument("--versions", type=int, default=600)
    parser.add_argument("--attachments", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", default="default")
    parser.add_argument("--skip-space-create", action="store_true",
                        help="Bereich existiert schon (z. B. manuell angelegt)")
    parser.add_argument("--sleep", type=float, default=0.1,
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

    rng = random.Random(args.seed)

    if not args.skip_space_create:
        if not create_space(client, args.space_key, args.space_name):
            return 1
        print(f"Bereich {args.space_key} angelegt.")

    homepage_id = get_homepage_id(client, args.space_key)
    if not args.quiet:
        print(f"Startseite: {homepage_id}")

    nodes = build_tree(rng, args.pages)
    targets = version_targets(rng, len(nodes), args.versions)

    page_ids: list = []
    created_pages = 0
    created_versions = 0
    for idx, (title, parent_idx) in enumerate(nodes):
        parent_id = homepage_id if parent_idx is None else page_ids[parent_idx]
        existing = find_page(client, args.space_key, title)
        if existing:
            page_ids.append(existing)
            if not args.quiet:
                print(f"[{idx + 1}/{len(nodes)}] übersprungen (existiert): {title}")
            continue
        page = client.create_page(
            args.space_key, title, page_markdown(rng, title, 1), parent_id
        )
        page_id = page["id"]
        page_ids.append(page_id)
        created_pages += 1
        created_versions += 1
        time.sleep(args.sleep)

        for version in range(2, targets[idx] + 1):
            update_page(
                client, page_id, title, version,
                page_markdown(rng, title, version),
            )
            created_versions += 1
            time.sleep(args.sleep)
        if not args.quiet:
            print(
                f"[{idx + 1}/{len(nodes)}] {title} "
                f"({targets[idx]} Versionen)"
            )

    created_attachments = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for n in range(args.attachments):
            target_page = rng.choice(page_ids)
            path = make_attachment_file(rng, tmp_dir, n)
            client.upload_attachment(str(target_page), str(path), "Testdaten v1")
            created_attachments += 1
            # ~30% get a second attachment version (same filename)
            if rng.random() < 0.3 and path.suffix != ".png":
                path.write_text(paragraph(rng) + "\n", encoding="utf-8")
                client.upload_attachment(
                    str(target_page), str(path), "Testdaten v2"
                )
            time.sleep(args.sleep)
            if not args.quiet and (n + 1) % 10 == 0:
                print(f"Anhänge: {n + 1}/{args.attachments}")

    print("\nFertig:")
    print(f"  Seiten neu angelegt: {created_pages} (von {len(nodes)} geplant)")
    print(f"  Seitenversionen erzeugt: {created_versions}")
    print(f"  Anhänge hochgeladen: {created_attachments}")
    print(
        f"  Bereich: {client.base_url}/display/{args.space_key}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
