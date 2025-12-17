# /// script
# requires-python = ">=3.12"
# ///
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# --- CONFIGURATION ---
INPUT_PAIRS = Path("pairs.json")
OUTPUT_PLAN = Path("move_plan.json")
OUTPUT_DIR = Path("Output")

def get_json_date(json_path):
    """Reads photoTakenTime from Google Takeout JSON. Returns timestamp (float)."""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # We ONLY use photoTakenTime as requested
        ts_taken = data.get('photoTakenTime', {}).get('timestamp')
        if ts_taken:
            return float(ts_taken)
            
    except Exception as e:
        print(f"Error reading JSON {json_path}: {e}")
        pass
    return None

# Fields where we merge (keep non-empty value, or special merge logic)
MERGE_PREFER_PRESENT = {'appSource', 'people', 'description', 'googlePhotosOrigin'}

def _is_empty(v):
    """Check if a value is considered 'empty'."""
    return v is None or v == '' or v == [] or v == {}

def _is_zero_geodata(geo):
    """Check if geoData has all zero values."""
    if not isinstance(geo, dict):
        return False
    return (geo.get('latitude', 0) == 0.0 and
            geo.get('longitude', 0) == 0.0 and
            geo.get('altitude', 0) == 0.0 and
            geo.get('latitudeSpan', 0) == 0.0 and
            geo.get('longitudeSpan', 0) == 0.0)

def cleanup_json(data):
    """Remove empty/useless fields from JSON for cleaner output."""
    if not isinstance(data, dict):
        return data
    
    result = dict(data)
    
    # Remove empty description
    if result.get('description') == '':
        del result['description']
    
    # Remove zero-valued geoData
    if 'geoData' in result and _is_zero_geodata(result['geoData']):
        del result['geoData']
        
    # Remove zero-valued geoDataExif (same check)
    if 'geoDataExif' in result and _is_zero_geodata(result['geoDataExif']):
        del result['geoDataExif']
    
    return result

def compute_md5(filepath):
    """Compute MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def verify_no_cross_duplicates(pairs, final_plan):
    """
    Verify that identical files (by content) all map to the same destination.
    Groups source files by size, then by MD5 hash, and checks destinations.
    """
    print("\n" + "="*40)
    print("CROSS-FILE DUPLICATE VERIFICATION")
    print("="*40)

    # Build a map: src_path -> dest_path from the plan
    src_to_dest = {}
    by_size = defaultdict(list)

    for entry in final_plan:
        src = entry['src']
        dest = entry['dest']

        try:
            size = os.path.getsize(src)
            src_to_dest[src] = dest
            by_size[size].append(src)
        except:
            pass
    
    # Now for each size group with >1 file, compute hashes and check
    cross_dupe_issues = []
    sizes_checked = 0
    files_hashed = 0
    
    for size, src_list in sorted(by_size.items()):
        if len(src_list) <= 1:
            continue
        
        sizes_checked += 1
        
        # Compute hashes for this size group
        hash_to_files = defaultdict(list)
        for src in src_list:
            try:
                h = compute_md5(src)
                files_hashed += 1
                hash_to_files[h].append(src)
            except Exception as e:
                print(f"  WARN: Cannot hash {src}: {e}")
        
        # Check if files with same hash go to different destinations
        for h, files in hash_to_files.items():
            if len(files) <= 1:
                continue
            
            dests = set(src_to_dest.get(f) for f in files)
            if len(dests) > 1:
                cross_dupe_issues.append({
                    'hash': h,
                    'size': size,
                    'files': files,
                    'destinations': list(dests)
                })
    
    print(f"Size groups checked: {sizes_checked}")
    print(f"Files hashed:        {files_hashed}")
    print(f"Cross-dupe issues:   {len(cross_dupe_issues)}")
    
    if cross_dupe_issues:
        print("\n!!! POTENTIAL CROSS-FILE DUPLICATES !!!")
        for issue in cross_dupe_issues[:5]:  # Show first 5
            print(f"  Hash: {issue['hash'][:8]}... Size: {issue['size']}")
            print(f"  Files: {len(issue['files'])}")
            for f in issue['files'][:3]:
                print(f"    - {f} -> {src_to_dest.get(f)}")
            if len(issue['files']) > 3:
                print(f"    ... and {len(issue['files'])-3} more")
        if len(cross_dupe_issues) > 5:
            print(f"  ... and {len(cross_dupe_issues)-5} more issues")
    else:
        print("✓ No cross-file duplicates found!")
    
    print("="*40)
    return cross_dupe_issues

def _merge_dicts(d1, d2):
    """Merge two dicts by union of keys. Returns (merged, error) or (None, error_msg)."""
    if d1 is None:
        return d2, None
    if d2 is None:
        return d1, None
    if not isinstance(d1, dict) or not isinstance(d2, dict):
        if d1 == d2:
            return d1, None
        return None, f"Cannot merge non-dicts: {d1} vs {d2}"
    
    result = dict(d1)
    for k, v in d2.items():
        if k not in result:
            result[k] = v
        elif result[k] != v:
            # Nested conflict - try recursive merge if both are dicts
            if isinstance(result[k], dict) and isinstance(v, dict):
                merged_nested, err = _merge_dicts(result[k], v)
                if err:
                    return None, err
                result[k] = merged_nested
            else:
                return None, f"Nested key '{k}' conflict: {result[k]} vs {v}"
    return result, None

def merge_json_cluster(json_list):
    """
    Attempts to merge multiple JSON dicts into one "canonical" JSON.
    Returns (merged_json, None) on success, or (None, error_message) on conflict.
    
    Merge Rules:
    - imageViews: Sum all values.
    - creationTime: Take minimum (earliest).
    - url: Keep the one from entry with most imageViews.
    - MERGE_PREFER_PRESENT: Keep whichever is present/non-empty. For dicts, merge by union.
    - photoTakenTime: If diff is 1h (DST) or 7-8h (timezone), keep the larger timestamp.
    - Other fields: Must match exactly.
    """
    if not json_list:
        return {}, None
    if len(json_list) == 1:
        return json_list[0], None
    
    # --- Pre-compute aggregates for special fields ---
    # imageViews: sum
    total_views = 0
    max_views = 0
    max_views_idx = 0
    for idx, j in enumerate(json_list):
        views_str = j.get('imageViews', '0')
        try:
            views = int(views_str)
        except (ValueError, TypeError):
            views = 0
        total_views += views
        if views > max_views:
            max_views = views
            max_views_idx = idx
    
    # creationTime: take minimum (earliest)
    min_creation = None
    for j in json_list:
        ct = j.get('creationTime', {})
        ts_str = ct.get('timestamp') if ct else None
        if ts_str:
            try:
                ts = int(ts_str)
                if min_creation is None or ts < min_creation:
                    min_creation = ts
            except (ValueError, TypeError):
                pass
    
    # url: keep from entry with most views
    best_url = json_list[max_views_idx].get('url')
    
    # --- Start with first JSON as base ---
    merged = dict(json_list[0])
    
    # Apply special field aggregates
    merged['imageViews'] = str(total_views)
    if min_creation:
        merged['creationTime'] = {
            'timestamp': str(min_creation),
            'formatted': datetime.fromtimestamp(min_creation).strftime('%b %d, %Y, %I:%M:%S %p UTC')
        }
    if best_url:
        merged['url'] = best_url
    
    # --- Pairwise merge for other fields ---
    for other in json_list[1:]:
        all_keys = set(merged.keys()) | set(other.keys())
        
        for k in all_keys:
            # Skip pre-handled fields
            if k in ('imageViews', 'creationTime', 'url'):
                continue
                
            v1 = merged.get(k)
            v2 = other.get(k)
            
            if v1 == v2:
                continue  # Already match
                
            # --- Special Case: MERGE_PREFER_PRESENT fields ---
            if k in MERGE_PREFER_PRESENT:
                # Special handling for 'people': union of lists
                if k == 'people':
                    list1 = v1 if isinstance(v1, list) else []
                    list2 = v2 if isinstance(v2, list) else []
                    names1 = {p.get('name') for p in list1 if p.get('name')}
                    names2 = {p.get('name') for p in list2 if p.get('name')}
                    all_names = names1 | names2
                    merged[k] = [{'name': n} for n in sorted(all_names)]
                    continue
                
                # Special handling for 'googlePhotosOrigin': merge dicts by union
                if k == 'googlePhotosOrigin':
                    merged_origin, err = _merge_dicts(v1, v2)
                    if err:
                        return None, f"googlePhotosOrigin merge failed: {err}"
                    merged[k] = merged_origin
                    continue
                    
                # Keep whichever is present/non-empty
                if _is_empty(v1) and not _is_empty(v2):
                    merged[k] = v2
                elif not _is_empty(v1) and _is_empty(v2):
                    pass  # Keep v1
                else:
                    return None, f"Field '{k}' conflict: both present but different"
                continue
                
            # --- Special Case: photoTakenTime ---
            if k == 'photoTakenTime':
                ts1 = int(v1.get('timestamp', 0)) if v1 else 0
                ts2 = int(v2.get('timestamp', 0)) if v2 else 0
                diff_hours = abs(ts1 - ts2) / 3600.0
                
                # Check if diff is a known timezone offset
                # 1 hour = DST, 7-8 hours = UTC vs Pacific Time
                if 0.9 <= diff_hours <= 1.1 or 6.9 <= diff_hours <= 8.1:
                    # Keep the LARGER timestamp (UTC > PT)
                    if ts2 > ts1:
                        merged[k] = v2
                    continue
                else:
                    return None, f"photoTakenTime mismatch: {diff_hours:.1f} hours apart"
                
            # --- Default: Must match exactly ---
            if v1 is None and v2 is not None:
                merged[k] = v2
            elif v1 is not None and v2 is None:
                pass  # Keep v1
            else:
                # Both present but different - conflict!
                return None, f"Field '{k}' mismatch: {v1} vs {v2}"
    
    return merged, None

def _make_renamed(dest_dir, file_name, counter):
    p = Path(file_name)
    return dest_dir / f"{p.stem}_{counter}{p.suffix}"

def main():
    if not INPUT_PAIRS.exists():
        print(f"Error: {INPUT_PAIRS} not found.")
        return

    print(f"Reading {INPUT_PAIRS}...")
    with open(INPUT_PAIRS, 'r') as f:
        pairs = json.load(f)
        
    print(f"Loaded {len(pairs)} pairs. Starting Map-Reduce...")
    
    # --- PHASE 1: MAP ---
    # Goal: Calculate "Ideal Destination" for every file
    # mapped_groups = { "dest_path_str": [ {src, json, ts}, ... ] }
    
    mapped_groups = defaultdict(list)
    
    sorted_src_paths = sorted(pairs.keys())
    
    for i, src_str in enumerate(sorted_src_paths):
        if i % 5000 == 0:
            print(f"Mapping {i}/{len(pairs)}...")

        json_str = pairs[src_str]
        src_path = Path(src_str)
        
        if not src_path.exists():
            continue
            
        if not json_str:
            print(f"SKIP: No JSON for {src_str}")
            continue
            
        timestamp = get_json_date(json_str)
        if timestamp is None:
            print(f"SKIP: No Date in JSON for {src_str}")
            continue
            
        dt = datetime.fromtimestamp(timestamp)
        year_str = dt.strftime("%Y")
        month_str = dt.strftime("%m")
        
        file_name = src_path.name
        dest_path = OUTPUT_DIR / year_str / month_str / file_name
        
        mapped_groups[str(dest_path)].append({
            'src_path': str(src_path.absolute()),
            'json_path': str(Path(json_str).absolute()),
            'timestamp': timestamp,
            'file_size': os.path.getsize(src_path)
        })

    print(f"Mapping Complete. Found {len(mapped_groups)} unique potential destinations.")
    print("Starting Reduce (Duplicate Resolution)...")

    # --- PHASE 2: REDUCE ---
    # Goal: Resolve collisions (multiple files mapping to same dest)
    # Strategy:
    #   - Cluster by FILE SIZE (bytes) - same size implies same content.
    #   - Within each size-cluster, MERGE all JSONs into one canonical JSON.
    #   - Different size-clusters get renamed (_1, _2).
    #   - The merged JSON is preserved for later writing.
    
    final_plan = []
    skipped_duplicates = 0
    resolved_renames = 0
    
    # We sort keys to ensures deterministic ordering
    for dest_str in sorted(mapped_groups.keys()):
        candidates = mapped_groups[dest_str]
        
        # If only 1 candidate -> Simple Case (but still load JSON)
        if len(candidates) == 1:
            c = candidates[0]
            # Load the JSON for this single file
            try:
                with open(c['json_path'], 'r') as f:
                    single_json = json.load(f)
            except Exception as e:
                print(f"ERROR reading JSON {c['json_path']}: {e}")
                single_json = {}
            
            # Clean up the JSON
            single_json = cleanup_json(single_json)
            
            final_plan.append({
                'src': c['src_path'],
                'dest': dest_str,
                'timestamp': c['timestamp'],
                'provenance': [Path(c['src_path']).parent.name],
                'merged_json': single_json
            })
            continue
            
        # Multiple candidates for ONE destination filename.
        # 1. Cluster by File Size
        by_size = defaultdict(list)
        for c in candidates:
            by_size[c['file_size']].append(c)
            
        # 2. For each size cluster, load JSONs and MERGE into canonical JSON
        sorted_sizes = sorted(by_size.keys())
        
        base_dest = Path(dest_str)
        dest_parent = base_dest.parent
        dest_name = base_dest.name
        
        for idx, size in enumerate(sorted_sizes):
            cluster = by_size[size]
            
            # Load JSON content for all files in this cluster
            for c in cluster:
                try:
                    with open(c['json_path'], 'r') as f:
                        c['_json_data'] = json.load(f)
                except Exception as e:
                    print(f"ERROR reading JSON {c['json_path']}: {e}")
                    c['_json_data'] = {}
            
            # Try to merge all JSONs in this cluster
            json_list = [c['_json_data'] for c in cluster]
            merged_json, error = merge_json_cluster(json_list)
            
            if error:
                print(f"\n{'!'*50}")
                print(f"CRITICAL ERROR: JSON Merge Failed!")
                print(f"Destination: {dest_str}")
                print(f"File Size:   {size} bytes")
                print(f"Error:       {error}")
                print(f"Candidates:")
                for c in cluster:
                    print(f"  - {c['src_path']}")
                    print(f"    JSON: {c['json_path']}")
                print(f"{'!'*50}")
                raise ValueError(f"JSON merge failed: {error}")
            
            # Merge successful! 
            provenance_list = [Path(x['src_path']).parent.name for x in cluster]
            
            # Use timestamp from merged JSON (corrected for timezone if needed)
            ts = float(merged_json.get('photoTakenTime', {}).get('timestamp', cluster[0]['timestamp']))
            
            # Destination Name logic
            if idx == 0:
                final_dest_str = dest_str # Keep original name
            else:
                # Collision! Add suffix _1, _2
                final_dest_str = str(_make_renamed(dest_parent, dest_name, idx))
                resolved_renames += 1
                
            # Clean up the merged JSON
            merged_json = cleanup_json(merged_json)

            entry = {
                'src': cluster[0]['src_path'],  # Pick first file as canonical source (all same content)
                'dest': final_dest_str,
                'timestamp': ts,
                'provenance': provenance_list,
                'merged_json': merged_json  # Canonical JSON for this file
            }
            final_plan.append(entry)
            skipped_duplicates += (len(cluster) - 1)

    # --- REPORT ---
    print("\n" + "="*40)
    print("PLANNING COMPLETE")
    print(f"Total Sources: {len(pairs)}")
    print(f"Moves Planned: {len(final_plan)}")
    print(f"Duplicates:    {skipped_duplicates}")
    print(f"Renamed:       {resolved_renames}")
    
    with open(OUTPUT_PLAN, 'w') as f:
        json.dump(final_plan, f, indent=2)
        
    print(f"Saved plan to: {OUTPUT_PLAN}")
    print("="*40)
    
    # --- CROSS-FILE DUPLICATE CHECK ---
    verify_no_cross_duplicates(pairs, final_plan)

if __name__ == "__main__":
    main()
