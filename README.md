# mkvrg
Apply replaygain tags to matroska files without remuxing (gain is calculated using ffmpeg and tags are applied using mkvpropedit).

Bash script for analyzing audio tracks in matroska files with [ffmpeg](https://ffmpeg.org/) and applying [replaygain](https://wiki.hydrogenaud.io/index.php?title=ReplayGain_2.0_specification) gain and peak tags with [mkvpropedit](https://mkvtoolnix.download/), this avoids remuxing the matroksa file. 

With [mpv](https://mpv.io/), you can add [replaygain=track](https://mpv.io/manual/stable/#options-replaygain) to [mpv.conf](https://mpv.io/manual/stable/#files) to enable replaygain tag parsing.

With [VLC](https://www.videolan.org/vlc/), you can enable replaygain by clicking `Tools -> Preferences -> Audio -> Replay gain mode`.

Pass list of files or a directory to scan files, if you pass a directory it will recursively search in it for files.

It will only process files with these extensions: "mkv, mka, mk3d".

The default alrogrithm used for calculating gain and peak is ffmpeg's ebur128, this can be changed with the FFMPEGFILTER env variable.

Requires: ffmpeg mkvpropedit

examples:

    ./mkrvg --help                ; Shows help and a list of environment variables and exits.
    ./mkvrg                       ; Recursive search in current folder for matroska files.
    ./mkvrg test.mkv              ; Process test.mkv in current folder.
    ./mkvrg Videos/               ; Recursive search in Videos folder for matroska files.
    ./mkvrg test.mkv Videos/      ; Process test.mkv in current folder and recursive
                                    search in Videos folder for matroska files.
    FORCE=true ./mkvrg test.mkv   ; Process test.mkv even if it already has replaygain tags.
    MINSIZE=+100M ./mkvrg         ; Recursive search in current folder for matroska
                                    files larger than 100MiB.
    FFMPEGFILTER=loudnorm ./mkvrg ; Use loudnorm ffmpeg filter to scan found files.

## mkvrg_deprecated_do_not_use.py

This python script is outdated, use mkvrg instead.
