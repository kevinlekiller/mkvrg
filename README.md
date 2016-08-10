# mkvrg
Apply replaygain to mkv's without remuxing.

Bash script for analyzing mkv files with BS1770GAIN and applying replaygain information with mkvpropedit.  
Pass list of files or a directory to scan files, if you pass a directory it will recursively search in it for files.

Requires:  
bs1770gain, mkvpropedit, file, gnu grep, which, find, tr,  
(optional) mediainfo

Change settings inside the script.

examples:  
Recursive search in current folder for mkv files.  
`./mkvrg.sh`

Process test.mkv in current folder.  
`./mkvrg.sh test.mkv`

Recursive search in Videos folder for mkv files.  
`./mkvrg.sh Videos/`

Process test.mkv in current folder and recursive search in Videos folder for mkv files.  
`./mkvrg.sh test.mkv Videos/`
