# mkvrg
Apply EBU R128 (using ffmpeg) replaygain tags to matroska files without remuxing (using mkvtoolnix).

Bash script for analyzing audio tracks in matroska files with ffmpeg and applying replaygain (EBU r128) gain and peak information with mkvpropedit, this avoids remuxing the matroksa file.

Pass list of files or a directory to scan files, if you pass a directory it will recursively search in it for files.

It will only work on files with these extensions: "mkv, mka, mk3d".

There is a setting to automatically remux mp4 and mov files to mkv before processing with EBU R128.

Requires: ffmpeg, mkvpropedit

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

Process test.mkv even if it already has replaygain tags and its size is at least 100 MB.

`FORCE=true MINSIZE=+100M ./mkvrg test.mkv`

## mkvrg_deprecated_do_not_use.py

This python script is outdated, use mkvrg instead.
