import os
import sys
import json
from pathlib import Path
from collections import defaultdict
from collections import Counter

# --- CONFIGURATION ---
ALLOWED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp',  # Images
    '.heic', '.heif',                  # HEIF
    '.mp4', '.mov', '.m4v', '.3gp',    # Videos
    '.avi', '.mpg', '.mkv', '.wmv',    # More Videos
    '.divx', '.webm',                  # Even More Videos
    '.gif', '.bmp', '.tiff', '.tif',   # Other Images
    '.arw', '.cr2', '.dng', '.nef',    # RAW Formats (Sony, Canon, Adobe, Nikon)
    '.orf', '.raf', '.sr2', '.rw2',    # RAW Formats (Olympus, Fuji, Sony, Panasonic)
    '.mp',                             # Google Motion Photo (sometimes separate file)
}



def scan_directory(input_dir: Path):
    print(f"Scanning directory: {input_dir} ...")
    
    media_files = []
    json_files = []
    unknown_extensions = set()
    unknown_files_examples = {} # To show examples of unknown files
    ignored_count = 0
    ignored_examples = defaultdict(str)
    ignored_counts = Counter()
    
    for root, dirs, files in os.walk(input_dir):
        for name in files:
            file_path = Path(root) / name
            # Check for "._" Mac ghost files
            if name.startswith("._"):
                assert False, file_path
                ignored_count += 1
                continue
                
            ext = file_path.suffix.lower()
            
            if ext in ALLOWED_EXTENSIONS:
                media_files.append(str(file_path.absolute()))
            elif ext == '.json':
                json_files.append(str(file_path.absolute()))
            elif ext in IGNORED_EXTENSIONS:
                ignored_count += 1
                ignored_counts[ext] += 1
                ignored_examples[ext] = str(file_path)
            else:
                unknown_extensions.add(ext)
                if ext not in unknown_files_examples:
                    unknown_files_examples[ext] = str(file_path)

    # --- REPORT ---
    print("\n" + "="*40)
    print(f"Scan Complete.")
    print(f"Media Files Found: {len(media_files)}")
    print(f"JSON Files Found:  {len(json_files)}")
    print(f"Ignored Files:     {ignored_count}")
    print(f"Ignored counts:    {ignored_counts.most_common()}")
    print(f"Ignored examples:  {ignored_examples}")
    
    
    if unknown_extensions:
        print("\n" + "!"*40)
        print("WARNING: Found UNKNOWN file extensions!")
        print("!"*40)
        for ext in sorted(unknown_extensions):
            print(f"  {ext:<6} (e.g., {unknown_files_examples[ext]})")
        print("\nReview these. If they are photos/videos, add them to ALLOWED_EXTENSIONS.")
    else:
        print("\nNo unknown file types found. Clean scan!")

    # --- OUTPUT ---
    output_path = Path("file_list.json")
    output_data = {
        'media': media_files,
        'json': json_files
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nSaved scan results to: {output_path.absolute()}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 1_scan.py <path_to_takeout_directory>")
        sys.exit(1)
        
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: Directory not found: {input_path}")
        sys.exit(1)
        
    scan_directory(input_path)
