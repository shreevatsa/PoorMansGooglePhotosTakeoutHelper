#!/usr/bin/env python3
"""
Execute the move plan created by 3_calc_move.py.
Moves media files to their destinations and writes merged JSON metadata.
"""

import json
import os
import shutil
import sys
from pathlib import Path

# --- CONFIGURATION ---
INPUT_PLAN = Path("move_plan.json")

def main():
    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=" * 50)
        print("DRY RUN MODE - No files will be moved")
        print("=" * 50)

    if not INPUT_PLAN.exists():
        print(f"Error: {INPUT_PLAN} not found. Run 3_calc_move.py first.")
        sys.exit(1)

    print(f"Reading {INPUT_PLAN}...")
    with open(INPUT_PLAN, 'r') as f:
        plan = json.load(f)

    print(f"Loaded {len(plan)} moves to execute.\n")

    # Statistics
    success_count = 0
    error_count = 0
    skipped_count = 0
    errors = []

    for i, entry in enumerate(plan):
        if i % 1000 == 0:
            print(f"Processing {i}/{len(plan)}...")

        src = Path(entry['src'])
        dest = Path(entry['dest'])
        merged_json = entry['merged_json']

        # Check source exists
        if not src.exists():
            error_count += 1
            errors.append(f"Source not found: {src}")
            continue

        # Skip if destination already exists
        if dest.exists():
            skipped_count += 1
            if i < 10:  # Only print first few
                print(f"SKIP: Destination exists: {dest}")
            continue

        if not dry_run:
            try:
                # Create destination directory
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Move the media file (removes from source location)
                shutil.move(src, dest)

                # Set file's mtime to the photo timestamp
                timestamp = entry['timestamp']
                os.utime(dest, (timestamp, timestamp))  # (atime, mtime)

                # Write the merged JSON metadata with provenance
                json_dest = dest.parent / (dest.name + ".json")
                json_data = dict(merged_json)
                json_data['provenance'] = entry['provenance']
                with open(json_dest, 'w') as f:
                    json.dump(json_data, f, indent=2)

                success_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f"Error processing {src}: {e}")
        else:
            # Dry run - just count as success
            success_count += 1

    # --- FINAL REPORT ---
    print("\n" + "=" * 50)
    print("MOVE EXECUTION COMPLETE")
    print("=" * 50)
    print(f"Total planned:  {len(plan)}")
    print(f"Successful:     {success_count}")
    print(f"Skipped:        {skipped_count} (destination exists)")
    print(f"Errors:         {error_count}")

    if dry_run:
        print("\n(DRY RUN - no files were actually moved)")

    if errors:
        print("\n--- ERRORS ---")
        for err in errors[:10]:
            print(f"  {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    print("=" * 50)

if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python3 4_move.py [--dry-run]")
        print()
        print("Execute the move plan created by 3_calc_move.py")
        print()
        print("Options:")
        print("  --dry-run    Show what would be done without actually moving files")
        sys.exit(0)

    main()
