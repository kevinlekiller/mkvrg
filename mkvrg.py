#!/usr/bin/env python
"""Calculate Replaygain for all audio tracks in Matroska files and write the
appropriate track tags to said files"""

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


def main():
    utils = Utils()
    if not utils.files:
        utils.print_message("No files found to process.", utils.MNOTICE)
    xml_utils = XmlUtils(utils)
    mkvrg = Mkvrg(xml_utils)
    for cur_file in utils.files:
        mkvrg.process_file(cur_file)
    return 0


class Utils():
    MDEBUG = 4
    MERROR = 3
    MWARNING = 2
    MNOTICE = 1
    MINFO = 0

    VERBOSITY_SILENT = -1
    VERBOSITY_NORMAL = 0
    VERBOSITY_DEBUG = 1

    def __init__(self):
        self.opt_exit = ""
        self.verbosity = self.exit = self.minsize = self.verbosity = 0
        self.sample_peak = self.default_track = self.exit = self.force = self.verify = False
        args = self.__parse_args()
        self.__check_binaries()
        self.ref_loudness = self.__get_ref_loudness()
        if self.ref_loudness == "":
            self.print_message("Could not find reference replaygain loudness from bs1770gain.",
                               self.MERROR)
            exit(1)

        self.track_list_regex = re.compile("Stream\s*#\d+:(\d+).+?Audio")
        self.rg_integrated_regex = re.compile("([-\d.]+\s*LU)\s*$")
        self.rg_range_regex = re.compile("([-\d.]+\s*LUFS)\s*$")
        self.rg_peak_regex = re.compile("([-\d.]+)\s*$")
        self.files = []
        path = os.path
        for arg in args:
            if path.isdir(arg):
                self.__check_dir(arg),
            elif path.isfile(arg):
                self.__check_file(arg)
            else:
                self.print_message("This does not look like a valid path: " + arg, self.MNOTICE)
        del args

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

    def check_tags(self, path, first_check=True):
        """Check if matroska file has replaygain tags."""
        if self.verify == False:
            return True
        if first_check == True and self.force == True:
            self.print_message("Skipping replaygain tags check, --force is on.")
            return True
        if "ITU-R BS.1770" in self.run_command("mediainfo " + path +
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

    def run_command(self, command, stderr=None, universal_newlines=False):
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

    def __check_file(self, path):
        magic, encoding = mimetypes.guess_type(path)
        if "matroska" not in magic.lower():
            self.print_message("File does not seem to contain Matroska data.", self.MERROR)
            return
        if self.minsize > 0 and os.path.getsize(path) < self.minsize:
            self.print_message("The file is smaller than your --minsize setting, skipping.", self.MNOTICE)
            return
        self.files.extend([path])

    def __check_dir(self, directory):
        for rootdir, dirnames, filenames in os.walk(directory):
            files = fnmatch.filter(filenames, '*.[mM][kK][aAvV]')
            files.extend(fnmatch.filter(filenames, '*.[mM][kK]3[dD]'))
            for filename in files:
                self.__check_file(os.path.join(rootdir, filename))

    def __do_exit(self, code=1):
        """Exit if --exit option is enabled."""
        if self.exit:
            self.print_message("The --exit option is enabled, exiting.", self.MNOTICE)
            exit(code)

    def __get_ref_loudness(self):
        """Get default replaygain reference loudness from bs1770gain."""
        buf = self.run_command("bs1770gain --help", stderr=subprocess.STDOUT)
        if not buf:
            return False
        buf = re.search("\(([-\d.]+\s+LUFS), default\)", buf)
        if "LUFS" not in buf.group(1):
            return False
        return buf.group(1)

    def __parse_args(self):
        """Parse command line arguments."""
        parser = ArgumentParser()
        parser.add_argument("-s", "--samplepeak", help="Use the sample peak option instead of true" +
                                                       " peak for bs1770gain, this is much faster.",
                            action="store_true")
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
                            help="Level of verbosity. (0 = normal, -1 = silent, 1 = debug).", default=0,
                            choices=[-1, 0, 1])
        parser.add_argument("paths", help="Path(s) to folder(s) or file(s) to scan matroska files for replaygain info.",
                            nargs="*")
        args = parser.parse_args()
        self.sample_peak = args.samplepeak
        self.default_track = args.default
        self.exit = args.exit
        self.force = args.force
        self.minsize = args.minsize
        if self.minsize < 0:
            self.print_message("The --minsize value must be a positive number.", self.MERROR)
            self.print_message("Setting --minsize to 0", self.MNOTICE)
            self.minsize = 0

        self.verify = args.verify
        if self.verify and not self.__check_binary("mediainfo"):
            self.print_message("You enabled the --verify option but you do not have mediainfo installed.",
                               self.MERROR)
            self.print_message("Setting --verify to false.", self.MNOTICE)
            self.verify = False

        self.verbosity = args.verbosity
        if not args.paths:
            self.print_message("No path(s) given, processing current working directory recursively.", self.MINFO)
            return ["."]
        return args.paths

    def __check_binary(self, binary):
        """Check if a binary is in PATH."""
        result = True
        devnull = open(os.devnull, 'w')
        try:
            subprocess.call([binary], stdout=devnull, stderr=devnull)
        except OSError as e:
            result = False
        devnull.close()
        return result

    def __check_binaries(self):
        """Check if all required binaries are in PATH."""
        binaries = ["bs1770gain", "mkvpropedit"]
        for binary in binaries:
            if not self.__check_binary(binary):
                self.print_message("The program '" + binary + "' is required.", self.MERROR)
                exit(1)


class MakeTmpFile:
    def __init__(self):
        """Create temp file."""
        self.handle, self.path = tempfile.mkstemp()

    def __del__(self):
        """Deletes temp file and closes handle on destruct."""
        if os.path.isfile(self.path):
            os.remove(self.path)
        if self.handle:
            os.close(self.handle)

    def clear(self):
        """Clears the contents of the temporary file."""
        if os.path.getsize(self.path) != 0:
            os.ftruncate(self.handle, 0)
            os.lseek(self.handle, 0, os.SEEK_SET)


class XmlUtils:
    def __init__(self, utils):
        self.utils = utils

    def set_rg_head(self):
        self.tags = xml.Element("Tags")
        self.tag = xml.SubElement(self.tags, "Tag")
        xml.SubElement(self.tag, "Targets")
        simple = xml.SubElement(self.tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_ALGORITHM"
        xml.SubElement(simple, "String").text = "ITU-R BS.1770"
        simple = xml.SubElement(self.tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_REFERENCE_LOUDNESS"
        xml.SubElement(simple, "String").text = self.utils.ref_loudness

    def set_rg_tags(self, rg_integrated, rg_range, rg_peak):
        if self.tags == None or self.tag != None:
            self.set_rg_head()
        simple = xml.SubElement(self.tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_TRACK_GAIN"
        xml.SubElement(simple, "String").text = rg_integrated
        simple = xml.SubElement(self.tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_TRACK_RANGE"
        xml.SubElement(simple, "String").text = rg_range
        simple = xml.SubElement(self.tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_TRACK_PEAK"
        xml.SubElement(simple, "String").text = rg_peak

    def write_rg_xml(self, path):
        if self.tag == None or self.tags == None:
            return
        xml.ElementTree(self.tags).write(path)
        self.tag = self.tags = None


class Mkvrg:
    def __init__(self,xml_utils):
        self.xml_utils = xml_utils
        self.utils = self.xml_utils.utils
        self.track_count = 0
        self.track = {}
        self.cur_path = self.rg_integrated = self.rg_range = self.rg_peak = ""
        self.mk_tmp = MakeTmpFile()
        self.tmp_file = self.mk_tmp.path

    def process_file(self, path):
        """Process a matroska file, analyzing it with bs1770gain and applying tags."""
        self.cur_path = path
        self.utils.print_message("Processing file: " + self.cur_path)
        if not self.utils.check_tags(self.cur_path):
            return
        self.__get_tracks()
        self.__process_tracks()

    def __get_tracks(self):
        self.utils.print_message("Getting tracks list.", self.utils.MDEBUG)
        """Get audio track numbers from bs1770gain"""
        buf = StringIO(self.utils.run_command("bs1770gain -l " + self.cur_path, subprocess.STDOUT, universal_newlines=True))
        self.tracks = {}
        i = 0
        for line in buf:
            if "Audio" in line and "Stream" in line:
                i += 1
                if self.utils.default_track == True and "default" not in line:
                    self.utils.print_message("Skipping non default audio track " + str(i) + ", you enabled --default")
                    continue
                matches = self.utils.track_list_regex.search(line)
                if not matches:
                    self.utils.print_message("Problem finding track number for track " + str(i), self.utils.MWARNING)
                    continue
                self.tracks[i] = matches.group(1)

    def __process_tracks(self):
        self.utils.print_message("Processing audio tracks.", self.utils.MDEBUG)
        if not self.tracks:
            self.utils.print_message("No audio tracks found in the file.", self.utils.MERROR)
            return False
        for tracknum, trackid in self.tracks.items():
            self.utils.print_message("Found track number: " + str(tracknum) + ", track id: " + trackid, self.utils.MDEBUG)
            if not self.__get_bs1770gain_info(trackid):
                continue
            if not self.__write_xml_file():
                continue
            self.__apply_tags(trackid)
        self.utils.check_tags(False)

    def __get_bs1770gain_info(self, trackid):
        self.utils.print_message("Getting replaygain info for track id " + trackid, self.utils.MDEBUG)
        handle = subprocess.Popen("bs1770gain --audio " + trackid + " -r " + ("-p " if self.utils.sample_peak else "-t ") +
                                  self.cur_path, stdout=subprocess.PIPE, shell=True)
        if not handle:
            self.utils.print_message("Problem running bs1770gain.", self.utils.print_message)
            return False
        lines = ""
        while True:
            line = handle.stdout.read(1)
            if line == "" and handle.poll() != None:
                break
            if line != "":
                lines = lines + line
                if self.utils.verbosity != self.utils.VERBOSITY_SILENT:
                    sys.stdout.write(line)

                sys.stdout.flush()
        lines = StringIO(lines)
        if not lines:
            self.utils.print_message("Problem parsing bs1770gain output.", self.utils.MERROR)
            return False
        self.rg_integrated = self.rg_range = self.rg_peak = ""
        for line in lines:
            if "ALBUM" in line:
                break
            elif "integrated" in line and self.rg_integrated == "":
                matches = self.utils.rg_integrated_regex.search(line)
                if not matches:
                    break
                self.rg_integrated = matches.group(1)
            elif "range" in line and self.rg_range == "":
                matches = self.utils.rg_range_regex.search(line)
                if not matches:
                    break
                self.rg_range = matches.group(1)
            elif "peak" in line and self.rg_peak == "":
                matches = self.utils.rg_peak_regex.search(line)
                if not matches:
                    break
                self.rg_peak = matches.group(1)
        if not self.rg_integrated or not self.rg_peak or not self.rg_range:
            self.utils.print_message("Could not find replaygain info from bs1770gain.", self.utils.MERROR)
            return False

        self.utils.print_message("Found replaygain info (integrated: " + self.rg_integrated +
                       ") (range: " + self.rg_range + ") (truepeak: " + self.rg_peak + ")", self.utils.MDEBUG)
        return True

    def __write_xml_file(self):
        """Write XML file with tags to temp file, for mkvpropedit."""
        self.utils.print_message("Writing XML file to " + self.tmp_file, self.utils.MDEBUG)
        self.mk_tmp.clear()
        self.xml_utils.set_rg_head()
        self.xml_utils.set_rg_tags(self.rg_integrated, self.rg_range, self.rg_peak)
        self.xml_utils.write_rg_xml(self.tmp_file)
        if os.path.getsize(self.tmp_file) == 0:
            self.utils.print_message("Could not write XML to temp file.", self.utils.MERROR)
            return False
        return True

    def __apply_tags(self, trackid):
        """Apply replaygain tags with mkvpropedit."""
        self.utils.print_message("Applying tags with mkvpropedit for track id " + trackid, self.utils.MDEBUG)
        if not self.utils.run_command("mkvpropedit --tags track:" + str(int(trackid) + 1) + ":" + self.tmp_file + " " +
                                          self.cur_path):
            self.utils.print_message("Problem applying replaygain tags to " + self.cur_path, self.utils.MERROR)
            return False
        return True

if __name__ == '__main__':
    main()
