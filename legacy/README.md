# Legacy Files

This folder contains older versions of scripts that have been superseded by unified versions.

## Files

### confluence-create-fzf-only.sh.backup
Original version of `confluence-create.sh` that required fzf.
**Replaced by:** Unified `confluence-create.sh` (works with or without fzf)

### confluence-create-simple.sh
Menu-based version of page creator (no fzf required).
**Replaced by:** Unified `confluence-create.sh` (auto-detects fzf)

### confluence-fzf-backup.sh
Backup of intermediate version of `confluence-fzf.sh`.
**Replaced by:** Unified `confluence-fzf.sh`

### confluence-fzf-original.sh.backup
Original version of `confluence-fzf.sh` that required fzf.
**Replaced by:** Unified `confluence-fzf.sh` (works with or without fzf)

### confluence-new.sh
Wrapper script that auto-selected between fzf and simple versions.
**No longer needed:** Main scripts now auto-detect

## Why Deprecated?

All functionality has been merged into the main scripts:

- **confluence-create.sh** - Now works with or without fzf
- **confluence-fzf.sh** - Now works with or without fzf

Both scripts automatically detect if fzf is available and use the appropriate UI.

## Can I Delete These?

Yes! These files are kept only for reference. If you don't need them, you can safely delete the entire `legacy/` folder:

```bash
rm -rf legacy/
```

## Migration

If you were using any of these old scripts, simply switch to the unified versions:

**Old:**
```bash
./confluence-create-simple.sh    # For systems without fzf
./confluence-new.sh               # Wrapper script
```

**New:**
```bash
./confluence-create.sh            # Works everywhere!
```

The new unified scripts provide the same functionality with automatic detection.
