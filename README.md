Alternative to Google Photos Takeout Helper.

A succession of scripts:

1. 1_scan.py: Scans a directory and identifies media files (non-.json files) in it.

2. 2_pair.py: Pairs media files with their metadata files (json files). For every media file, there should be exactly one JSON file. (But not vice-versa: some JSON files are shared.)

3. 3_calc.py: Uses the JSON data to reorganize the media files into year/month directories, keeping the current directories in JSON. This can be used to create a move plan.

4. 4_move.py: Moves the media files to the year/month directories based on the move plan.