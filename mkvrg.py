#!/usr/bin/env python

import sys
import os
import fnmatch
import magic
import enzyme
from argparse import ArgumentParser


def main(argv):
    mkvrg = Mkvrg("mkvrg")
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
        self.mkv_info = []

    def start(self, args):
        """Sort through paths to see if they are directories or normal files."""
        path = os.path
        for arg in args:
            if path.isdir(arg):
                self.process_dir(arg),
            elif path.isfile(arg):
                self.process_file(arg)
            else:
                self.print_message("This does not look like a valid path: " + arg, self.MNOTICE)

    def process_dir(self, directory):
        """Find mkv/mkva/mk3d files in directories"""
        for rootdir, dirnames, filenames in os.walk(directory):
            files = fnmatch.filter(filenames, '*.[mM][kK][aAvV]')
            files.extend(fnmatch.filter(filenames, '*.[mM][kK]3[dD]'))
            for filename in files:
                self.process_file(os.path.join(rootdir, filename))

    def process_file(self, path):
        """Process a matroska file, analyzing it with bs1770gain and applying tags."""
        self.cur_path = path
        self.print_message("Processing file: " + self.cur_path)
        if not self.test_matroska(self.cur_path):
            self.print_message("File is not matroska.", self.MWARNING)
            self.do_exit()
            return
        if not self.get_mkvinfo():
            return

    def get_mkvinfo(self):
        with open(self.cur_path, "rb") as handle:
            mkv = enzyme.MKV(handle)
        tracks = len(mkv.audio_tracks)
        if not tracks:
            self.print_message("Could not find number of audio tracks.", self.MWARNING)
            self.do_exit()
            return
        self.print_message("The file has " + str(tracks) + " audio tracks.", self.MDEBUG)
        for track in range(0, tracks):
           self.print_message("Track: " + str(mkv.audio_tracks[track].number), self.MDEBUG)


    def check_tags(self, path, first_check=True):
        """Check if matroska file has replaygain tags."""
        if self.verify == False :
            return
        if first_check == True and self.force == True:
            return
        print()

    def do_exit(self, code=1):
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

    @staticmethod
    def test_matroska(path):
        """Test if file is Matroska data."""
        with magic.Magic() as m:
            if "matroska" in m.id_filename(path).lower():
                return True
        return False

if __name__ == '__main__':
    main(sys.argv)
