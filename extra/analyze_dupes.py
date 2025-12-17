#!/usr/bin/env python3
"""Quick script to analyze the size of cross-file duplicates."""

import json
import hashlib
from pathlib import Path
from collections import defaultdict

def compute_md5(filepath):
    """Compute MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

# Read the move plan
with open('move_plan.json', 'r') as f:
    plan = json.load(f)

print(f"Analyzing {len(plan)} planned moves...")

# Group by (size, hash) to find duplicates going to different destinations
by_size = defaultdict(list)

for entry in plan:
    src = entry['src']
    dest = entry['dest']

    try:
        size = Path(src).stat().st_size
        by_size[size].append((src, dest))
    except:
        pass

print(f"Found {len(by_size)} unique file sizes")

# Now check size groups with multiple files
total_duplicate_size = 0
total_wasted_space = 0
duplicate_count = 0

for size, files in by_size.items():
    if len(files) <= 1:
        continue

    # Compute hashes for this size group
    hash_groups = defaultdict(list)
    for src, dest in files:
        try:
            h = compute_md5(src)
            hash_groups[h].append((src, dest))
        except Exception as e:
            print(f"Error hashing {src}: {e}")

    # Check for duplicates going to different destinations
    for h, file_list in hash_groups.items():
        if len(file_list) <= 1:
            continue

        dests = set(dest for src, dest in file_list)
        if len(dests) > 1:
            # Cross-file duplicate!
            duplicate_count += len(file_list)
            total_duplicate_size += size * len(file_list)
            total_wasted_space += size * (len(file_list) - 1)

print(f"\n{'='*50}")
print(f"DUPLICATE FILE ANALYSIS")
print(f"{'='*50}")
print(f"Files involved in collisions: {duplicate_count}")
print(f"Total disk space used:        {total_duplicate_size:,} bytes ({total_duplicate_size / 1024**2:.1f} MB)")
print(f"Wasted space (duplicates):    {total_wasted_space:,} bytes ({total_wasted_space / 1024**2:.1f} MB)")
print(f"{'='*50}")
