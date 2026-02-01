"""
Unicode Encoding Fix Script
===========================
Replaces Unicode symbols in Python files that cause cp1252 encoding errors on Windows.

Run: python scripts/fix_unicode_encoding.py
"""

import os
import re
from pathlib import Path

# Replacement map: Unicode -> ASCII safe equivalent
REPLACEMENTS = {
    # Checkmarks and status
    "[OK]": "[OK]",
    "[OK]": "[OK]",
    "[OK]": "[OK]",
    "[OK]": "[OK]",
    "[FAIL]": "[FAIL]",
    "[FAIL]": "[FAIL]",
    "[FAIL]": "[FAIL]",
    "[FAIL]": "[FAIL]",
    "[FAIL]": "[FAIL]",
    
    # Warnings and info
    "[WARN]": "[WARN]",
    "[WARN]️": "[WARN]",
    "[STOP]": "[STOP]",
    "[STOP]": "[STOP]",
    "[INFO]": "[INFO]",
    "[INFO]️": "[INFO]",
    
    # Tools and actions
    "[FIX]": "[FIX]",
    "[BUILD]": "[BUILD]",
    "[SYNC]": "[SYNC]",
    "[REFRESH]": "[REFRESH]",
    "[CONFIG]": "[CONFIG]",
    "[CONFIG]️": "[CONFIG]",
    
    # Status indicators
    "[*]": "[*]",
    "[ ]": "[ ]",
    "[~]": "[~]",
    "[.]": "[.]",
    "[ ]": "[ ]",
    "[*]": "[*]",
    
    # Arrows
    "->": "->",
    "<-": "<-",
    "^": "^",
    "v": "v",
    "=>": "=>",
    "<=": "<=",
    
    # Trading specific
    "[UP]": "[UP]",
    "[DOWN]": "[DOWN]",
    "[$]": "[$]",
    "[$]": "[$]",
    "[TARGET]": "[TARGET]",
    "[LAUNCH]": "[LAUNCH]",
    "[CHART]": "[CHART]",
    "[LIST]": "[LIST]",
    "[DIR]": "[DIR]",
    "[FILE]": "[FILE]",
    
    # Misc
    "[LOCK]": "[LOCK]",
    "[UNLOCK]": "[UNLOCK]",
    "[KEY]": "[KEY]",
    "[IDEA]": "[IDEA]",
    "[TIME]": "[TIME]",
    "[ALARM]": "[ALARM]",
    "[WIN]": "[WIN]",
    "[SUCCESS]": "[SUCCESS]",
}

# Directories to skip
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}


def fix_file(filepath: Path) -> tuple[int, list[str]]:
    """
    Fix Unicode characters in a single file.
    
    Returns:
        Tuple of (replacement_count, list of changes made)
    """
    try:
        # Read with UTF-8
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Try with errors ignored
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return 0, [f"Error reading: {e}"]
    
    original = content
    changes = []
    total_replacements = 0
    
    for unicode_char, ascii_replacement in REPLACEMENTS.items():
        if unicode_char in content:
            count = content.count(unicode_char)
            content = content.replace(unicode_char, ascii_replacement)
            changes.append(f"  {unicode_char} -> {ascii_replacement} ({count}x)")
            total_replacements += count
    
    if content != original:
        # Write back with UTF-8 (still safe, but now ASCII-compatible)
        filepath.write_text(content, encoding="utf-8")
        return total_replacements, changes
    
    return 0, []


def scan_and_fix(root_dir: Path, dry_run: bool = False) -> dict:
    """
    Scan directory and fix all Python files.
    
    Args:
        root_dir: Root directory to scan
        dry_run: If True, only report changes without writing
    
    Returns:
        Summary dict with stats
    """
    stats = {
        "files_scanned": 0,
        "files_modified": 0,
        "total_replacements": 0,
        "changes": {},
    }
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            
            filepath = Path(dirpath) / filename
            stats["files_scanned"] += 1
            
            if dry_run:
                # Just check without modifying
                try:
                    content = filepath.read_text(encoding="utf-8")
                    found = []
                    for uc in REPLACEMENTS:
                        if uc in content:
                            found.append(f"{uc} ({content.count(uc)}x)")
                    if found:
                        stats["changes"][str(filepath)] = found
                        stats["files_modified"] += 1
                except Exception:
                    pass
            else:
                count, changes = fix_file(filepath)
                if count > 0:
                    stats["files_modified"] += 1
                    stats["total_replacements"] += count
                    stats["changes"][str(filepath)] = changes
    
    return stats


def main():
    import argparse
    import sys
    import io
    
    # Force UTF-8 stdout on Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    parser = argparse.ArgumentParser(description="Fix Unicode encoding issues in Python files")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without modifying files")
    parser.add_argument("--path", default=".", help="Root directory to scan (default: current)")
    args = parser.parse_args()
    
    root = Path(args.path).resolve()
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Scanning: {root}")
    print("-" * 60)
    
    stats = scan_and_fix(root, dry_run=args.dry_run)
    
    # Report
    for filepath, changes in stats["changes"].items():
        rel_path = Path(filepath).relative_to(root)
        print(f"\n{rel_path}:")
        for change in changes:
            print(f"  {change}")
    
    print("\n" + "=" * 60)
    print(f"Files scanned:  {stats['files_scanned']}")
    print(f"Files modified: {stats['files_modified']}")
    if not args.dry_run:
        print(f"Replacements:   {stats['total_replacements']}")
    print("=" * 60)
    
    if args.dry_run and stats["files_modified"] > 0:
        print("\nRun without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
