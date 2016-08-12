# mkvrg
Apply replaygain to matroska files without remuxing.

Bash script for analyzing audio tracks in matroska files with BS1770GAIN and applying replaygain (EBU r128) track/peak information with mkvpropedit.  
Pass list of files or a directory to scan files, if you pass a directory it will recursively search in it for files.
It will only work on files with these extensions: "mkv, mka, mk3d".

Requires:  
bs1770gain, mkvpropedit, file, gnu grep, which, find, tr,  
(optional) mediainfo

Currently (August 11 2016) optionally requires https://github.com/kevinlekiller/bs1770gain_fixes to work properly on matroska files with multiple audio tracks until bs1770gain is released with those fixes,
otherwise all the audio tracks will have the replaygain info from the last track.

Change settings inside the script.

examples:  
Recursive search in current folder for matroska files.  
`./mkvrg`

Process test.mkv in current folder.  
`./mkvrg test.mkv`

Recursive search in Videos folder for matroska files.  
`./mkvrg Videos/`

Process test.mkv in current folder and recursive search in Videos folder for matroska files.  
`./mkvrg test.mkv Videos/`
