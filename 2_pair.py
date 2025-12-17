import json
import sys
import unicodedata
from pathlib import Path

# --- CONFIGURATION ---
INPUT_LIST = Path("file_list.json")
OUTPUT_PAIRS = Path("pairs.json")



def find_json_for_file(file_path: Path):
    """
    Tries multiple strategies to find the corresponding JSON file.
    Returns the Path to the JSON if found, else None.
    """
    parent = file_path.parent
    name = file_path.name
    stem = file_path.stem # filename without extension
    
    # --- HELPER HELPER ---
    def check_variants(path_candidate_base: Path):
        """Helper to try common suffixes"""
        suffixes = [
            ".json",
            ".supplemental-metadata.json",
            ".supplemental-metadat.json",
            ".supplemental-metada.json",
            ".supplemental-metad.json",
            ".supplemental-meta.json",
            ".supplemental-met.json",
            ".supplemental-me.json",
            ".supplemental-m.json",
            ".supplemental-.json",
            ".supplemental.json",
            ".supplementa.json",
            ".supplement.json",
            ".supplemen.json",
            ".suppleme.json",
            ".supplem.json",
            ".suppl.json",
            ".supp.json",
        ]

        for s in suffixes:
            c = path_candidate_base.parent / (path_candidate_base.name + s)
            if c.exists(): return c

        return None

    # --- MAIN SEARCH LOGIC ---
    # Heuristic 1: Exact Match (most common)
    # image.jpg -> image.jpg.json
    res = check_variants(parent / name)
    if res: return res
        
    # 1.1 Burst Logic: _CO.jpg -> _C.json
    if stem.endswith("_CO"):
        # try _C.json
        c_stem = stem[:-2] + "C"
        c = parent / (c_stem + ".json")
        if c.exists(): return c
        
    # 2. Match without extension (Critical for some files like '3_11_15 - 1')
    # image.jpg -> image.supplemental-metadata.json
    res = check_variants(parent / stem)
    if res: return res
    
    # 2.5 Sibling matching for .MP files (file.MP -> file.MP.jpg.json)
    if file_path.suffix.lower() == '.mp':
        res = check_variants(parent / (name + ".jpg"))
        if res: return res
        
    # 3. Truncated 46 chars (Heuristic 3 - Restored)
    # Awesome...Ide.jpg -> Awesome...Id.json
    if len(name) > 46:
        trunc_name = name[:46]
        res = check_variants(parent / trunc_name)
        if res: return res
        
    # 3. Complex logic: Strip "Extra stuff"
    clean_stem = stem
    dup_number = None
    
    # 3a. Strip Duplicate Number (Bracket, Tilde, or " - N")
    # Check for (N) at end
    if "(" in clean_stem and clean_stem.endswith(")"):
        try:
            base, num = clean_stem.rsplit('(', 1)
            num = num.rstrip(')')
            if num.isdigit():
                clean_stem = base.strip() # Handle "file (1)" -> "file"
                dup_number = num
        except ValueError:
            pass
    # Check for ~N at end (if not found above)
    elif "~" in clean_stem:
        try:
            base, num = clean_stem.rsplit('~', 1)
            if num.isdigit():
                clean_stem = base.strip()
                dup_number = num
        except ValueError:
            pass
    # Check for " - N" at end
    elif " - " in clean_stem: # NEW: Handle "file - 1.jpg"
        try:
            base, num = clean_stem.rsplit(' - ', 1)
            if num.isdigit():
                clean_stem = base.strip()
                dup_number = num
        except ValueError:
            pass
            
    # --- INTERMEDIATE CHECK: Duplicates on "Collage" names ---
    # Before we strip the suffix (e.g. -COLLAGE), let's check if we have a duplicate
    # on the current clean_stem (which might still be "IMG...-COLLAGE")
    if dup_number:
         # Base: IMG...-COLLAGE.jpg
         # Check IMG...-COLLAGE.jpg.supplemental-m(1).json
         
         # Reuse the matrix logic logic here using a helper or just inline copy
         # Since we have the dup number, let's try.
         base_file_intermediate = clean_stem + file_path.suffix
         
         # Combo 1: Standard Bracket
         c = parent / (base_file_intermediate + f"({dup_number}).json")
         if c.exists(): return c
         
         # Combo 2: Typo Matrix
         candidates = [
            f".supplemental-metadata({dup_number}).json",
            f".supplemental-metadat({dup_number}).json",
            f".supplemental-metada({dup_number}).json",
            f".supplemental-metad({dup_number}).json",
            f".supplemental-meta({dup_number}).json",
            f".supplemental-met({dup_number}).json",
            f".supplemental-me({dup_number}).json",
            f".supplemental-m({dup_number}).json",
            f".supplemental-({dup_number}).json",
            f".supplemental({dup_number}).json", 
            f".supplementa({dup_number}).json",
            f".supplement({dup_number}).json",
            f".supplemen({dup_number}).json",
            f".suppleme({dup_number}).json",
            f".supplem({dup_number}).json",
            f".suppl({dup_number}).json",
            f".supp({dup_number}).json",
            f".json({dup_number})", 
        ]
         for suffix in candidates:
             c = parent / (base_file_intermediate + suffix)
             if c.exists(): return c
            
    # 3b. Strip Edited/Collage Suffix
    # 3b. Strip Edited/Collage Suffix (Recursively for cases like -EFFECTS-edited)
    suffixes = ['-edited', '-modifié', '-kopio', '-löschen', ' copy', '-COLLAGE', '-EFFECTS']
    while True:
        original_stem = clean_stem
        lower_s = clean_stem.lower()
        for s in suffixes:
            if lower_s.endswith(s.lower()):
                 # Use slicing based on suffix length to avoid finding 's' in the middle
                 # We established it ends with it.
                 clean_stem = clean_stem[:-len(s)]
                 break # Break inner loop to re-evaluate
        
    
        # If no change in this pass, we are done
        if clean_stem == original_stem:
            break
            
        # INTERMEDIATE CHECK: Did we find the match after stripping one level?
        # e.g. "image-EFFECTS-edited.jpg" -> "image-EFFECTS.jpg"
        # The JSON might be "image-EFFECTS.jpg.json"
        check_intermediate = clean_stem + file_path.suffix
        res = check_variants(parent / check_intermediate)
        if res: return res
        
    # Now we have a candidate "Clean" name (e.g. "image") and potentially a "Dup Number" (e.g. "1")
    # Let's try to match JSONs.
    
    base_file = clean_stem + file_path.suffix # image.jpg
    
    assert dup_number is not None
    if True:
        # We need to check both WITH extension (base_file) and WITHOUT extension (clean_stem)
        # Because "hemlatha(1).jpg" -> "hemlatha.supplemental-metadata(1).json" (No .jpg)
        
        bases_to_try = [base_file, clean_stem]
        
        for base in bases_to_try:
            # Combo 1: JSON has the number in its name (Old style)
            # image.jpg(1).json
            c = parent / (base + f"({dup_number}).json")
            if c.exists(): return c
            
            # Combo 2: JSON has the number in metadata parens (New style)
            # image.jpg.supplemental-metadata(1).json
            
            candidates = [
                f".supplemental-metadata({dup_number}).json",
                f".supplemental-metada({dup_number}).json",
                f".supplemental-metad({dup_number}).json",
                f".supplemental-metadat({dup_number}).json",
                f".supplemental-met({dup_number}).json",
                f".supplemental-me({dup_number}).json",
                f".supplemental-m({dup_number}).json",
                f".supplemental-meta({dup_number}).json",
                f".supplement({dup_number}).json",
                f".supplemental({dup_number}).json", 
                f".json({dup_number})", # Rare
            ]
            
            for suffix in candidates:
                 c = parent / (base + suffix)
                 if c.exists(): return c
                 
        return None

def main():
    if not INPUT_LIST.exists():
        print(f"Error: {INPUT_LIST} not found. Run 1_scan.py first.")
        sys.exit(1)
        
    print(f"Reading {INPUT_LIST}...")
    with open(INPUT_LIST, 'r') as f:
        data = json.load(f)
        
    # Backward compatibility handle
    if isinstance(data, list):
        media_files = data
        all_json_files = set() # No json list in old format
    else:
        media_files = data.get('media', [])
        all_json_files = set(data.get('json', []))
        
    pairs = {}
    found_count = 0
    missing_count = 0
    used_json = set()
    
    print(f"Processing {len(media_files)} media files...")
    
    for i, fpath_str in enumerate(media_files):
        if i % 1000 == 0:
            print(f"Pairing {i}/{len(media_files)}...")
            
        fpath = Path(fpath_str)
        json_path = find_json_for_file(fpath)
        
        if json_path:
            json_abs = str(json_path.absolute())
            pairs[fpath_str] = json_abs
            used_json.add(json_abs)
            found_count += 1
        else:
            pairs[fpath_str] = None
            missing_count += 1
            
    # Calculate Orphans
    orphans = all_json_files - used_json
    
    # --- REPORT ---
    print("\n" + "="*40)
    print("Pairing Complete.")
    print(f"Total Media:  {len(media_files)}")
    print(f"JSON Paired:  {found_count}")
    print(f"JSON Miss:    {missing_count}")
    print(f"Unused JSON:  {len(orphans)}")
    
    output_path = OUTPUT_PAIRS
    with open(output_path, 'w') as f:
        json.dump(pairs, f, indent=2)
        
    print(f"\nSaved pairs to: {output_path.absolute()}")
    
    if len(orphans) > 0:
        print("\n--- Example Unused JSONs (Orphans) ---")
        for o in list(orphans)[:10]:
             print(f"ORPHAN: {o}")
        print(f"(and {len(orphans)-10} more)")

    if missing_count > 0:
        print(f"\nNote: {missing_count} files have no JSON.")
        print("--- Example Misses ---")
        miss_sample = [k for k, v in pairs.items() if v is None][:10]
        for m in miss_sample:
            print(f"MISS: {m}")

if __name__ == "__main__":
    main()
