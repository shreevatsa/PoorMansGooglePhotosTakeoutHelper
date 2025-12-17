#!/usr/bin/env python3
"""
Verify that all remaining media files in the original directory are duplicates.
"""

import json
import os
from pathlib import Path
from collections import defaultdict

# Same extensions as 1_scan.py
ALLOWED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp',
    '.heic', '.heif',
    '.mp4', '.mov', '.m4v', '.3gp',
    '.avi', '.mpg', '.mkv', '.wmv',
    '.divx', '.webm',
    '.gif', '.bmp', '.tiff', '.tif',
    '.arw', '.cr2', '.dng', '.nef',
    '.orf', '.raf', '.sr2', '.rw2',
    '.mp',
}

# Load the move plan to see which files were moved
print("Loading move_plan.json...")
with open('move_plan.json', 'r') as f:
    plan = json.load(f)

moved_files = set(entry['src'] for entry in plan)
print(f"Files that were moved: {len(moved_files)}")

# Load the original pairs to see all media files
print("Loading pairs.json...")
with open('pairs.json', 'r') as f:
    pairs = json.load(f)

all_media_files = set(pairs.keys())
print(f"Total media files originally: {len(all_media_files)}")

# Calculate expected remaining files
expected_remaining = all_media_files - moved_files
print(f"Expected remaining (duplicates): {len(expected_remaining)}")

# Now scan the original directory for remaining files
takeout_dir = Path.home() / "Downloads/amma-photos/Takeout/Google Photos"
print(f"\nScanning {takeout_dir}...")

remaining_files = []
for root, dirs, files in os.walk(takeout_dir):
    for name in files:
        file_path = Path(root) / name
        ext = file_path.suffix.lower()

        if ext in ALLOWED_EXTENSIONS:
            remaining_files.append(str(file_path.absolute()))

print(f"Media files still in Takeout: {len(remaining_files)}")

# Check if they match expectations
remaining_set = set(remaining_files)
unexpected = remaining_set - expected_remaining
missing = expected_remaining - remaining_set

print("\n" + "="*50)
print("VERIFICATION RESULTS")
print("="*50)
print(f"Expected remaining:  {len(expected_remaining)}")
print(f"Actually remaining:  {len(remaining_set)}")
print(f"Unexpected files:    {len(unexpected)}")
print(f"Missing files:       {len(missing)}")

if unexpected:
    print("\n!!! UNEXPECTED FILES (should have been moved?) !!!")
    for f in list(unexpected)[:10]:
        print(f"  {f}")
    if len(unexpected) > 10:
        print(f"  ... and {len(unexpected) - 10} more")

if missing:
    print("\n!!! MISSING FILES (expected to remain but don't exist?) !!!")
    for f in list(missing)[:10]:
        print(f"  {f}")
    if len(missing) > 10:
        print(f"  ... and {len(missing) - 10} more")

if not unexpected and not missing:
    print("\n✓ All remaining files are exactly the duplicates we expected!")
    print("✓ It's safe to delete the Takeout directory.")

print("="*50)
