# mkvrg
Apply replaygain to matroska files without remuxing.

Bash script for analyzing audio tracks in matroska files with ffmpeg and applying replaygain (EBU r128) gain/peak information with mkvpropedit.
Pass list of files or a directory to scan files, if you pass a directory they will recursively search in it for files.
They will only work on files with these extensions: "mkv, mka, mk3d".

Requires: ffmpeg, ffprobe, mkvpropedit

Change settings inside the script. You can also set environment variables to change settings on a per call basis.

examples:
Recursive search in current folder for matroska files.  
`./mkvrg`

Process test.mkv in current folder.  
`./mkvrg test.mkv`

Recursive search in Videos folder for matroska files.  
`./mkvrg Videos/`

Process test.mkv in current folder and recursive search in Videos folder for matroska files.  
`./mkvrg test.mkv Videos/`

Process test.mkv but only if it has no tags yet and its size is at least 100 MB.

`VERIFY=true FORCE=false MINSIZE=+100M ./mkvrg`

## mkvrg_deprecated_do_not_use.py

This python script is outdated, use mkvrg instead.
