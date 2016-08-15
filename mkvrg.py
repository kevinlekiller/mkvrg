#!/usr/bin/env python

from __future__ import print_function
import sys
import os
import fnmatch
import subprocess
import shlex
import re
import tempfile
import mimetypes
import xml.etree.cElementTree as xml
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from argparse import ArgumentParser


def main(argv):
    mkvrg = Mkvrg()
    check_binaries(mkvrg)
    mkvrg.start(parse_args(mkvrg))
    return 0


def parse_args(mkvrg):
    """Parse command line arguments."""
    parser = ArgumentParser()
    parser.add_argument("-d", "--default", help="Only process the default audio track?", action="store_true")
    parser.add_argument("-m", "--minsize", type=int, help="Minimum size of matroska file in bytes.", default=0)
    parser.add_argument("-c", "--verify",
                        help="Verify if matroska file has replaygain tags before and after analyzing.",
                        action="store_true")
    parser.add_argument("-f", "--force",
                        help="Force scanning files for replaygain, even if they already have replaygain tags.",
                        action="store_true")
    parser.add_argument("-e", "--exit", help="Stop and exit if any problems are encountered.", action="store_true")
    parser.add_argument("-v", "--verbosity", type=int,
                        help="Level of verbosity. (0 = normal, -1 = silent, 1 = debug).", default=0, choices=[-1,0,1])
    parser.add_argument("paths", help="Path(s) to folder(s) or file(s) to scan matroska files for replaygain info.",
                        nargs="*")
    args = parser.parse_args()
    mkvrg.default_track = args.default
    mkvrg.exit = args.exit
    mkvrg.force = args.force
    mkvrg.minsize = args.minsize
    if mkvrg.minsize < 0:
        mkvrg.print_message("The --minsize value must be a positive number.", mkvrg.MERROR)
        mkvrg.print_message("Setting --minsize to 0", mkvrg.MNOTICE)
        mkvrg.minsize = 0
    mkvrg.verify = args.verify
    if mkvrg.verify and not check_binary("mediainfo"):
        mkvrg.print_message("You enabled the --verify option but you do not have mediainfo installed.", mkvrg.MERROR)
        mkvrg.print_message("Setting --verify to false.", mkvrg.MNOTICE)
        mkvrg.verify = False
    mkvrg.verbosity = args.verbosity
    if not args.paths:
        mkvrg.print_message("No path(s) given, processing current working directory recursively.", mkvrg.MINFO)
        return ["."]
    return args.paths


def check_binaries(mkvrg):
    """Check if all required binaries are in PATH."""
<<<<<<< HEAD
    binaries = ["bs1770gain", "mkvpropedit", "file"]
=======
    binaries = ["bs1770gain", "mkvpropedit"]
>>>>>>> refs/remotes/origin/python
    for binary in binaries:
        if not check_binary(binary):
            mkvrg.print_message("The program '" + binary + "' is required.", mkvrg.MERROR)
            exit(1)


def check_binary(binary):
    """Check if a binary is in PATH."""
    result = True
    try:
        devnull = open(os.devnull, 'w')
        subprocess.call([binary], stdout=devnull, stderr=devnull)
    except OSError as e:
        result = False
    devnull.close()
    return result

class Mkvrg:
    VERBOSITY_SILENT = -1
    VERBOSITY_NORMAL = 0
    VERBOSITY_DEBUG = 1

    MDEBUG = 4
    MERROR = 3
    MWARNING = 2
    MNOTICE = 1
    MINFO = 0

    def __init__(self):
        self.default_track = self.exit = self.force = self.verify = False
        self.minsize = 0
        self.verbosity = self.VERBOSITY_NORMAL

        self.cur_path = ""
        self.track_count = 0
        self.track = {}

        self.tmp_file = ""
        self.tmp_handle = None
        self.__make_temp_file()

        self.ref_loudness = self.integrated = self.range = self.true_peak = ""
        self.__get_ref_loudness()
        if self.ref_loudness == "":
            self.print_message("Could not find reference replaygain loudness from bs1770gain.", self.MERROR)
            exit(1)

    def __del__(self):
        """Cleans temp file on destruct."""
        if os.path.isfile(self.tmp_file):
            os.remove(self.tmp_file)
        if self.tmp_handle:
            os.close(self.tmp_handle)

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

    def __get_ref_loudness(self):
        """Get default replaygain reference loudness from bs1770gain."""
        buf = self.__run_command("bs1770gain --help", stderr=subprocess.STDOUT)
        if not buf:
            return
        buf = re.search("\(([-\d.]+\s+LUFS), default\)", buf)
        if "LUFS" not in buf.group(1):
            return
        self.ref_loudness = buf.group(1)

    def __make_temp_file(self):
        self.tmp_handle, self.tmp_file = tempfile.mkstemp()

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
        self.print_message("Processing file: " + self.cur_path)
        if "matroska" not in mimetypes.guess_type(self.cur_path).lower():
            self.print_message("File does not seem to contain Matroska data.", self.MERROR)
            return
        if self.minsize > 0 and os.path.getsize(self.cur_path) < self.minsize:
            self.print_message("The file is smaller than your --minsize setting, skipping.", self.MNOTICE)
            return
        if not self.__check_tags():
            return
        self.__get_tracks()
        self.__process_tracks()

    def __get_tracks(self):
        self.print_message("Getting tracks list.", self.MDEBUG)
        """Get audio track numbers from bs1770gain"""
        buf = StringIO(self.__run_command("bs1770gain -l " + self.cur_path, subprocess.STDOUT, universal_newlines=True))
        self.tracks = {}
        i = 0
        for line in buf:
            if "Audio" in line and "Stream" in line:
                i += 1
                if self.default_track == True and "default" not in line:
                    self.print_message("Skipping non default audio track " + str(i) + ", you enabled --default")
                    continue
                matches = re.search("Stream\s*#\d+:(\d+).+?Audio", line)
                if not matches:
                    self.print_message("Problem finding track number for track " + str(i), self.MWARNING)
                    continue
                self.tracks[i] = matches.group(1)

    def __process_tracks(self):
        self.print_message("Processing audio tracks.", self.MDEBUG)
        if not self.tracks:
            self.print_message("No audio tracks found in the file.", self.MERROR)
            return False
        for tracknum, trackid in self.tracks.items():
            self.print_message("Found track number: " + str(tracknum) + ", track id: " + trackid, self.MDEBUG)
            if not self.__get_bs1770gain_info(trackid):
                continue
            if not self.__write_xml_file():
                continue
            self.__apply_tags(trackid)
        self.__check_tags(False)

    def __get_bs1770gain_info(self, trackid):
        self.print_message("Getting replaygain info for track id " + trackid, self.MDEBUG)
        handle = subprocess.Popen("bs1770gain --audio " + trackid + " -rt " + self.cur_path, stdout=subprocess.PIPE,
                                  shell=True)
        if not handle:
            self.print_message("Problem running bs1770gain.", self.MERROR)
            return False
        lines = ""
        while True:
            line = handle.stdout.read(1)
            if line == "" and handle.poll() != None:
                break
            if line != "":
                lines = lines + line
                sys.stdout.write(line)
                sys.stdout.flush()
        lines = StringIO(lines)
        if not lines:
            self.print_message("Problem parsing bs1770gain output.", self.MERROR)
            return False
        self.integrated = self.range = self.true_peak = ""
        for line in lines:
            if "ALBUM" in line:
                break
            elif "integrated" in line and self.integrated == "":
                matches = re.search("([-\d.]+\s*LU)\s*$", line)
                if not matches:
                    break
                self.integrated = matches.group(1)
            elif "range" in line and self.range == "":
                matches = re.search("([-\d.]+\s*LUFS)\s*$", line)
                if not matches:
                    break
                self.range = matches.group(1)
            elif "true peak" in line and self.true_peak == "":
                matches = re.search("([-\d.]+)\s*$", line)
                if not matches:
                    break
                self.true_peak = matches.group(1)
        if not self.integrated or not self.true_peak or not self.range:
            self.print_message("Could not find replaygain info from bs1770gain.", self.MERROR)
            return False
        self.print_message("Found replaygain info (integrated: " + self.integrated +
                           ") (range: " + self.range + ") (truepeak: " + self.true_peak + ")", self.MDEBUG)
        return True

    def __write_xml_file(self):
        """Write XML file with tags to temp file, for mkvpropedit."""
        self.print_message("Writing XML file to " + self.tmp_file, self.MDEBUG)
        self.__clr_tmp_file()
        tags = xml.Element("Tags")
        tag = xml.SubElement(tags, "Tag")
        xml.SubElement(tag, "Targets")
        simple = xml.SubElement(tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_ALGORITHM"
        xml.SubElement(simple, "String").text = "ITU-R BS.1770"
        simple = xml.SubElement(tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_REFERENCE_LOUDNESS"
        xml.SubElement(simple, "String").text = self.ref_loudness
        simple = xml.SubElement(tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_TRACK_GAIN"
        xml.SubElement(simple, "String").text = self.integrated
        simple = xml.SubElement(tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_TRACK_RANGE"
        xml.SubElement(simple, "String").text = self.range
        simple = xml.SubElement(tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_TRACK_PEAK"
        xml.SubElement(simple, "String").text = self.true_peak
        xml.ElementTree(tags).write(self.tmp_file)
        if os.path.getsize(self.tmp_file) == 0:
            self.print_message("Could not write XML to temp file.", self.MERROR)
            return False
        return True

    def __clr_tmp_file(self):
        if os.path.getsize(self.tmp_file) != 0:
            os.ftruncate(self.tmp_handle, 0)
            os.lseek(self.tmp_handle, 0, os.SEEK_SET)

    def __apply_tags(self, trackid):
        """Apply replaygain tags with mkvpropedit."""
        self.print_message("Applying tags with mkvpropedit for track id " + trackid, self.MDEBUG)
        if not self.__run_command("mkvpropedit --tags track:" + str(int(trackid) + 1) + ":" + self.tmp_file + " " +
                                          self.cur_path):
            self.print_message("Problem applying replaygain tags to " + self.cur_path, self.MERROR)
            return False
        return True

    def __check_tags(self, first_check=True):
        """Check if matroska file has replaygain tags."""
        if self.verify == False :
            return True
        if first_check == True and self.force == True:
            self.print_message("Skipping replaygain tags check, --force is on.")
            return True
        if "ITU-R BS.1770" in self.__run_command("mediainfo " + self.cur_path +
                                                         ' --Inform="Audio;%REPLAYGAIN_ALGORITHM%"'):
            self.print_message("Replaygain tags found in file.")
            if first_check:
                return False
            return True
        if first_check == True:
            self.print_message("No replaygain tags found in file.")
            return True
        self.print_message("No replaygain tags found in file.", self.MERROR)
        return False

    def __do_exit(self, code=1):
        """Exit if --exit option is enabled."""
        if self.exit:
            self.print_message("The --exit option is enabled, exiting.", self.MNOTICE)
            exit(code)

    def print_message(self, message, mtype=MINFO):
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
            self.__do_exit()
        elif mtype == self.MDEBUG:
            print("\033[95mDEBUG: " + message + "\033[0m")

    def __run_command(self, command, stderr=None, universal_newlines=False):
        """Run a command in a shell, return the output as a string."""
        ret = ""
        try:
            ret = str(subprocess.check_output(shlex.split(command), stderr=stderr,
                                              universal_newlines=universal_newlines))
        except subprocess.CalledProcessError as e:
            ""
        except OSError as e:
            ""
        return ret

if __name__ == '__main__':
    main(sys.argv)
