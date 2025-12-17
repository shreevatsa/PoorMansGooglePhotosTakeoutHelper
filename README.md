# The problem

If you have data on [Google Photos](https://photos.google.com/), it can be exported using [Google Takeout](https://takeout.google.com/). This is what my mother did (or I did on behalf of my mother) when her Google account was running out of space. The export has two problems:

- The media files (photos and videos) are in a bunch of different locations: they are in directories called:

  ```
  Takeout/Google Photos/Photos from 2022
  Takeout/Google Photos/Photos from 2023
  Takeout/Google Photos/Photos from 2024
  Takeout/Google Photos/Photos from 2025
  ```

  etc, and also in directories named by the album they were in:

  ```
  Takeout/Google Photos/Saturday afternoon in Mysore
  Takeout/Google Photos/Seattle trip
  ```

  etc.

- The media files have associated metadata that comes in "sidecar" `.json` files, and it's not entirely straightforward which JSON file contains the metadata for which media file.

So, if exporting to another storage/backup location, it may be preferable to:

- have the files simply in dated directories (`YYYY/MM/`),
- de-duplicated,
- with the associated JSON data being clearly matched to the file (and moved in when possible, e.g. set the file's mtime to the "correct" date, not the time of the Takeout export),
- and still retain the album information (which file was in which album) somehow (just in case we can find a use for it later), so that it is not entirely lost.

# The standard solution

The “standard” solution is I believe [the repository called Google Photos Takeout Helper](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper): for example, the help page [How do I migrate photos from Google Photos to Synology Photos?](https://kb.synology.com/en-in/DSM/tutorial/How_do_I_migrate_photos_from_Google_Photos).

If this works for you, great!

I tried it but it didn't handle 100% of the files (some were left behind and not moved to the output folder, and it's not clear to me whether it was because they were duplicates or there was some issue: there were indeed a bunch of warnings about files for which a date was not found), and more importantly I couldn't understand what it was doing, and I didn't want to lose any data.

Edit: It turns out the repo actually (as of today 2025-12-17) has known issues wherein it fails to handle the current format of Takeout JSON; see e.g. [this search](https://github.com/search?q=repo%3ATheLastGimbus%2FGooglePhotosTakeoutHelper+supplemental&type=issues). There are PRs on the repo and presumably forks of this repo (which was last updated late 2025-Jan as of the time I'm writing this) that fix this problem, but that would explain why it didn't work for me.

# This solution

The scripts here in this repo are very crude, but at least I understand them, and they're very paranoid about not missing anything. (They were written with some combination of AI tools, but also read and edited by me manually.) They are organized as a succession of short, simple, easy-to-understand scripts:

1. 1_scan.py: Scans the source directory and identifies every media (non-JSON) file and JSON file in it. Simply lists them; produces `file_list.json`, which is simply of the form:

  ```
  {
    "media": [
      "/path/to/file1.jpg",
      "/path/to/file2.mp4",
      ...
    ],
    "json": [
      "/path/to/json1.json",
      "/path/to/json2.json",
      ...
    ]
}
  ```

2. 2_pair.py: Pairs media files with their metadata files (json files). For every media file, there should be exactly one JSON file. (But not vice-versa: some JSON files are shared.) Produces a `pairs.json`, which is of the form:

  ```
  {
    "/path/to/file1.jpg": "/path/to/json1.json",
    "/path/to/file2.mp4": "/path/to/json2.json",
    ...
  }
  ```

  The filenames produced by Google Takeout have various kinds of truncation for length (look at the script yourself), so this is nontrivial.

3. 3_calc.py: The longest script: uses the above data to generate a "move plan", i.e. it handles 

   - deciding on the "correct" date for each file (after a lot of back and forth and exploring the files I had, for my use case I decided to simply use the "taken" field from the JSON; you may want to defer to one of the fields of EXIF data if it seems more accurate: it wasn't in my case)
   - merging (in a very conservative/paranoid way) the metadata from different (duplicate) files going to the same destination path,
   - deciding a "destination" path for each file with (some amount of) deduplication (there was still about 0.7% of duplicates left where the duplicate files had different dates; I decided to just let them be rather than lose the metadata),
   - retaining the original "provenance" (all of the “albums” (directories) that the media file was part of).
  
   It does this by writing out a `move_plan.json`, which looks like:

   ```
    [
      {
        "src": "/path/to/file1.jpg",
        "dest": "Output/path/to/file1.jpg",
        "timestamp": 1230793200.0,
        "provenance": [
          "San bruno lake_"
        ],
        "merged_json": {
          ...
        }
      },
      ...
    ]
   ```
   
4. 4_move.py: Actually executes the `move_plan.json` generated above, i.e. moves each files to the corresponding destination directory, keeps the metadata JSON next to it (this time in a consistent format), and updates file mtime to the correct time. Note: You may additionally also want to write the metadata (time and location information) from the JSON into the file's EXIF data itself; I missed doing that. But the data is there so I can do it later if needed.
