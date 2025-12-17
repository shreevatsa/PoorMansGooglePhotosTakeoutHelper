#!/usr/bin/env python3
"""
Add provenance field to existing JSON files.
"""

import json
from pathlib import Path

INPUT_PLAN = Path("move_plan.json")

def main():
    print(f"Reading {INPUT_PLAN}...")
    with open(INPUT_PLAN, 'r') as f:
        plan = json.load(f)

    print(f"Loaded {len(plan)} entries. Updating JSON files...\n")

    success_count = 0
    error_count = 0
    errors = []

    for i, entry in enumerate(plan):
        if i % 1000 == 0:
            print(f"Processing {i}/{len(plan)}...")

        dest = Path(entry['dest'])
        provenance = entry['provenance']
        json_path = dest.parent / (dest.name + ".json")

        if not json_path.exists():
            error_count += 1
            errors.append(f"JSON not found: {json_path}")
            continue

        try:
            # Read existing JSON
            with open(json_path, 'r') as f:
                data = json.load(f)

            # Add provenance field
            data['provenance'] = provenance

            # Write back
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)

            success_count += 1

        except Exception as e:
            error_count += 1
            errors.append(f"Error updating {json_path}: {e}")

    # --- FINAL REPORT ---
    print("\n" + "=" * 50)
    print("PROVENANCE UPDATE COMPLETE")
    print("=" * 50)
    print(f"Total files:    {len(plan)}")
    print(f"Updated:        {success_count}")
    print(f"Errors:         {error_count}")

    if errors:
        print("\n--- ERRORS ---")
        for err in errors[:10]:
            print(f"  {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    print("=" * 50)

if __name__ == "__main__":
    main()
