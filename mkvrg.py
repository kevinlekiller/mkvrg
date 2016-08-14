#!/usr/bin/env python


# Issues: enzyme returns the "track number" like mkvinfo does, but bs1770gain requires the "track ID"
# Might need to drop enzyme

import sys
import os
import fnmatch
import magic
import enzyme
import subprocess
from argparse import ArgumentParser


def main(argv):
    mkvrg = Mkvrg("mkvrg")
    check_binaries(mkvrg)
    mkvrg.start(parse_args(mkvrg))
    return 0


def parse_args(mkvrg):
    """Parse command line arguments."""
    parser = ArgumentParser()
    parser.add_argument("-d", "--default", help="Only process the default audio track?", action="store_true")
    parser.add_argument("-m", "--minsize", type=int, help="Minimum size of matroska file in MB", default=0)
    parser.add_argument("-c", "--verify", help="Verify if matroska file has replaygain tags before and after analyzing.", action="store_true")
    parser.add_argument("-f", "--force", help="Force scanning files for replaygain, even if they already have replaygain tags.", action="store_true")
    parser.add_argument("-e", "--exit", help="Stop and exit if any problems are encountered during file processing.", action="store_true")
    parser.add_argument("-v", "--verbosity", type=int, help="Level of verbosity. (0 = normal, -1 = silent, 1 = debug).", default=0, choices=[-1,0,1])
    parser.add_argument("paths", help="Path(s) to folder(s) or file(s) to scan matroska files for replaygain info.", nargs="*")
    args = parser.parse_args()
    mkvrg.default_track = args.default
    mkvrg.exit = args.exit
    mkvrg.force = args.force
    mkvrg.minsize = args.minsize
    mkvrg.verify = args.verify
    mkvrg.verbosity = args.verbosity
    if not args.paths:
        mkvrg.print_message("No path(s) given, processing current working directory recursively.", mkvrg.MINFO)
        return ["."]
    return args.paths


def check_binaries(mkvrg):
    """Check if all required binaries are in PATH."""
    binaries = ["which", "bs1770gain", "mkvpropedit"]
    for binary in binaries:
        if not check_binary(binary):
            mkvrg.print_message("The program '" + binary + "' is required.", mkvrg.MERROR)
            exit(1)


def check_binary(binary):
    """Check if a binary is in PATH."""
    try:
        devnull = open(os.devnull, 'w')
        if subprocess.call(["which", binary], stdout=devnull, stderr=subprocess.STDOUT) != 0:
            devnull.close()
            return False
        devnull.close()
    except OSError as e:
        return False
    return True

class Mkvrg:
    VERBOSITY_SILENT = -1
    VERBOSITY_NORMAL = 0
    VERBOSITY_DEBUG = 1

    MDEBUG = 4
    MERROR = 3
    MWARNING = 2
    MNOTICE = 1
    MINFO = 0

    def __init__(self, name):
        self.name = name
        self.default_track = False
        self.exit = False
        self.force = False
        self.minsize = 0
        self.verbosity = self.VERBOSITY_NORMAL
        self.verify = False

        self.cur_path = ""
        # For mkvpropedit
        self.cur_tracknum = 0
        # For bs1770gain
        self.cur_trackid = 0
        self.mkv_info = []
        self.track_count = 0

    def start(self, args):
        """Sort through paths to see if they are directories or normal files."""
        path = os.path
        for arg in args:
            if path.isdir(arg):
                self.__process_dir(arg),
            elif path.isfile(arg):
                self.__process_file(arg)
            else:
                self.print_message("This does not look like a valid path: " + arg, self.MNOTICE)

    def __process_dir(self, directory):
        """Find mkv/mkva/mk3d files in directories"""
        for rootdir, dirnames, filenames in os.walk(directory):
            files = fnmatch.filter(filenames, '*.[mM][kK][aAvV]')
            files.extend(fnmatch.filter(filenames, '*.[mM][kK]3[dD]'))
            for filename in files:
                self.__process_file(os.path.join(rootdir, filename))

    def __process_file(self, path):
        """Process a matroska file, analyzing it with bs1770gain and applying tags."""
        self.cur_path = path
        self.cur_tracknum = 0
        self.cur_trackid = 0
        self.mkv_info = []
        self.print_message("Processing file: " + self.cur_path)
        if not self.test_matroska(self.cur_path):
            self.print_message("File is not matroska.", self.MWARNING)
            self.__do_exit()
            return
        if not self.__get_mkvinfo():
            return

    def __get_mkvinfo(self):
        """Get matroska information for current file."""
        try:
            with open(self.cur_path, "rb") as handle:
                self.mkv_info = enzyme.MKV(handle)
        except enzyme.exceptions.MalformedMKVError as e:
            return False
        except IOError as e:
            return False
        self.track_count = len(self.mkv_info.audio_tracks)
        if not self.track_count:
            self.print_message("Could not find number of audio tracks.", self.MWARNING)
            self.__do_exit()
            return False
        self.print_message("The file has " + str(self.track_count) + " audio tracks.", self.MDEBUG)
        self.__process_tracks()

    def __process_tracks(self):
        for track in range(0, self.track_count):
            self.cur_tracknum += 1
            self.cur_trackid = self.mkv_info.audio_tracks[track].number
            self.print_message("Track: " + str(self.cur_trackid), self.MDEBUG)
            if self.default_track == True:
                if self.mkv_info.audio_tracks[track].default == True:
                    self.__process_track()
                    continue
                else:
                    self.print_message("Skipping track " + str(self.cur_trackid) + ", --default option is on.", self.MINFO)
                    continue
            self.__process_track()

    def __process_track(self):
        """Run the track through bs1770gain and mkvpropedit, check if tags were applied."""
        if not self.__check_tags():
            return
        if not self.__analyze_track():
            return
        if not self.__apply_tags():
            return

    def __analyze_track(self):
        """Run bs1770gain on the file to get replaygain information."""
        self.run_command([
            "bs1770gain",
            "--audio", str(self.cur_trackid),
            " -rt ",
            self.cur_path
        ])

    def __apply_tags(self):
        """Apply replaygain tags with mkvpropedit."""

    def __check_tags(self, first_check=True):
        """Check if matroska file has replaygain tags."""
        if self.verify == False :
            return True
        if first_check == True and self.force == True:
            self.print_message("Skipping replaygain tags check, --force is on.", self.MINFO)
            return True
        if not len(self.mkv_info.tags) and first_check == False:
            self.print_message("No tags at all found in the file.", self.MERROR)
            self.__do_exit()
            return False
        if "ITU-R BS.1770" in str(self.mkv_info.tags):
            self.print_message("Replaying tags found in file.", self.MINFO)
            return True
        if first_check == True:
            self.print_message("No replaygain tags found in file.", self.MINFO)
            return True
        self.print_message("No replaygain tags found in file.", self.MERROR)
        self.__do_exit()
        return False

    def __do_exit(self, code=1):
        """Exit if --exit option is enabled."""
        if self.exit:
            self.print_message("The --exit option is enabled, exiting.", self.MINFO)
            exit(code)

    def print_message(self, message, mtype=0):
        """Print message with colors, appends type of message."""
        if self.verbosity == self.VERBOSITY_SILENT:
            return
        if mtype == self.MDEBUG and self.verbosity != self.VERBOSITY_DEBUG:
            return
        if mtype == self.MINFO:
            print("INFO: " + message)
        elif mtype == self.MNOTICE:
            print("\033[92mNOTICE: " + message + "\033[0m")
        elif mtype == self.MWARNING:
            print("\033[93mWARNING: " + message + "\033\[0m")
        elif mtype == self.MERROR:
            print("\033[91mERROR: " + message + "\033[0m")
        elif mtype == self.MDEBUG:
            print("\033[95mDEBUG: " + message + "\033[0m")

    def run_command(self, command):
        try:
            print(str(subprocess.check_output(command)))
        except subprocess.CalledProcessError as e:
            return False


    @staticmethod
    def test_matroska(path):
        """Test if file is Matroska data."""
        with magic.Magic() as m:
            if "matroska" in m.id_filename(path).lower():
                return True
        return False

if __name__ == '__main__':
    main(sys.argv)
