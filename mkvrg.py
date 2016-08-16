#!/usr/bin/env python
"""Calculate Replaygain for all audio tracks in Matroska files and write the
appropriate track tags to said files"""

from __future__ import print_function
import os
import fnmatch
import subprocess
import shlex
import re
import tempfile
import multiprocessing
import itertools
import logging
import xml.etree.cElementTree as xml
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from argparse import ArgumentParser


def main():
    log = Log()
    utils = Utils()
    utils.log = log
    CheckArgs(utils)
    if not utils.files:
        utils.log.warning("No files found to process.")

    ThreadMkvrg(utils)
    return 0


def process_thread(thread, queue, utils):
    while True:
        work = queue.get()
        if not work:
            queue.task_done()
            return
        mkvrg = Mkvrg(utils, thread)
        mkvrg.process_file(work)
        queue.task_done()


class Log:
    def __init__(self, verbosity=20, name="mkvrg"):
        """"""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(verbosity)
        if not len(self.logger.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s [%(levelname)s]:\t%(message)s'))
            handler.setLevel(verbosity)
            self.logger.addHandler(handler)
        self.exit = False

    def set_verbosity(self, verbosity):
        self.logger.setLevel(verbosity)

    def log(self, level, message):
        self.logger.log(message)

    def critical(self, message):
        self.logger.critical(message)
        self.__do_exit()

    def debug(self, message):
        self.logger.debug(message)

    def error(self, message):
        self.logger.error(message)
        self.__do_exit()

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def __do_exit(self, code = 1):
        if self.exit:
            print("The --exit option is enabled, exiting.")
            exit(code)


class ThreadMkvrg:
    def __init__(self, utils):
        threads = utils.threads
        total_work = len(utils.files)
        if total_work < threads:
            threads = total_work

        manager = multiprocessing.Manager()
        queue = manager.Queue(threads)

        processes = []
        for i in range(threads):
            process = multiprocessing.Process(target=process_thread, args=(i, queue, utils))
            process.start()
            processes.append(process)

        iterator = itertools.chain(utils.files, (None,)*threads)
        for work in iterator:
            queue.put(work)

        for process in processes:
            process.join()


class CheckArgs:
    def __init__(self, utils):
        self.utils = utils
        self.__check_binaries()
        args = self.__parse_args()
        self.utils.log.exit = self.utils.exit
        self.utils.log.set_verbosity(self.utils.verbosity)
        self.utils.ref_loudness = self.__get_ref_loudness()
        if self.utils.ref_loudness == "":
            self.utils.log("Could not find reference replaygain loudness from bs1770gain.")
            exit(1)

        path = os.path
        for arg in args:
            if path.isdir(arg):
                self.__check_dir(arg),
            elif path.isfile(arg):
                self.__check_file(arg)
            else:
                self.utils.log.info("This does not look like a valid path: " + arg)

    def __parse_args(self):
        """Parse command line arguments."""
        parser = ArgumentParser()
        parser.add_argument("-s", "--samplepeak", help="Use the sample peak option instead of true" +
                            " peak for bs1770gain, this is much faster.",
                            action="store_true")
        parser.add_argument("-t", "--threads", type=int, help="Amount of threads to use to process files.", default=1)
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
                            help="Level of verbosity. (20 = info (default), 99 = silent, 10 = debug, " +
                                 "30 = warning, 40 = error, 50 = critical, 0 = all).", default=20,
                            choices=[20, 99, 10, 30, 40, 50, 0])
        parser.add_argument("paths", help="Path(s) to folder(s) or file(s) to scan matroska files for replaygain info.",
                            nargs="*")
        args = parser.parse_args()
        self.utils.verbosity = args.verbosity
        self.utils.sample_peak = args.samplepeak
        self.utils.default_track = args.default
        self.utils.exit = args.exit
        self.utils.force = args.force

        self.utils.threads = args.threads
        if self.utils.threads < 1:
            self.utils.log.error("The --threads must be at least 1")
            self.utils.log.error("Setting --threads to 1")
            self.utils.threads = 1

        self.utils.minsize = args.minsize
        if self.utils.minsize < 0:
            self.utils.log.error("The --minsize value must be a positive number.")
            self.utils.log.info("Setting --minsize to 0")
            self.utils.minsize = 0

        self.utils.verify = args.verify
        if self.utils.verify and not self.__check_binary("mediainfo"):
            self.utils.log.error("You enabled the --verify option but you do not have mediainfo installed.")
            self.utils.log.info("Setting --verify to false.")
            self.utils.verify = False

        if not args.paths:
            self.utils.log.info("No path(s) given, processing current working directory recursively.")
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
        binaries = ["bs1770gain", "mkvpropedit", "mkvinfo"]
        for binary in binaries:
            if not self.__check_binary(binary):
                print("ERROR: The program '" + binary + "' is required.")
                exit(1)

    def __check_file(self, path):
        self.utils.log.info("Checking file (" + path + ").")
        if not self.utils.run_command("mkvinfo " + path):
            self.utils.log.error("File does not seem to contain Matroska data.")
            return
        if self.utils.minsize > 0 and os.path.getsize(path) < self.utils.minsize:
            self.utils.log.info("The file is smaller than your --minsize setting, skipping.")
            return
        if not self.utils.check_tags(path):
            return
        self.utils.files.extend([path])

    def __check_dir(self, directory):
        for rootdir, dirnames, filenames in os.walk(directory):
            files = fnmatch.filter(filenames, '*.[mM][kK][aAvV]')
            files.extend(fnmatch.filter(filenames, '*.[mM][kK]3[dD]'))
            for filename in files:
                self.__check_file(os.path.join(rootdir, filename))

    def __get_ref_loudness(self):
        """Get default replaygain reference loudness from bs1770gain."""
        buf = self.utils.run_command("bs1770gain --help", stderr=subprocess.STDOUT)
        if not buf:
            return False
        buf = re.search("\(([-\d.]+\s+LUFS), default\)", buf)
        if "LUFS" not in buf.group(1):
            return False
        return buf.group(1)


class Utils:
    def __init__(self):
        self.opt_exit = ""
        self.verbosity = self.exit = self.minsize = self.verbosity = self.threads = 0
        self.loglevel = "INFO"
        self.sample_peak = self.default_track = self.exit = self.force = self.verify = False
        self.track_list_regex = re.compile(r"Stream\s*#\d+:(\d+).+?Audio")
        self.rg_integrated_regex = re.compile(r"([-\d.]+\s*LU)\s*$")
        self.rg_range_regex = re.compile(r"([-\d.]+\s*LUFS)\s*$")
        self.rg_peak_regex = re.compile(r"([-\d.]+)\s*$")
        self.files = []
        self.log = None

    def check_tags(self, path, first_check=True):
        """Check if matroska file has replaygain tags."""
        if not self.verify:
            return True
        if first_check and self.force:
            self.log.info("Skipping replaygain tags check, --force is on.")
            return True
        if "ITU-R BS.1770" in self.run_command("mediainfo " + path +
                                               ' --Inform="Audio;%REPLAYGAIN_ALGORITHM%"'):
            if first_check:
                self.log.info("Replaygain tags found in file (" + path + "), skipping.")
                return False
            return True
        if first_check:
            self.log.info("No replaygain tags found in file (" + path + ") continuing.")
            return True

        self.log.error("No replaygain tags were found in file (" + path + ") after applying with mkvpropedit.")
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
    def __init__(self, ref_loudness):
        """"""
        self.ref_loudness = ref_loudness
        self.tags = self.tag = None

    def set_rg_head(self):
        self.tags = xml.Element("Tags")
        self.tag = xml.SubElement(self.tags, "Tag")
        xml.SubElement(self.tag, "Targets")
        simple = xml.SubElement(self.tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_ALGORITHM"
        xml.SubElement(simple, "String").text = "ITU-R BS.1770"
        simple = xml.SubElement(self.tag, "Simple")
        xml.SubElement(simple, "Name").text = "REPLAYGAIN_REFERENCE_LOUDNESS"
        xml.SubElement(simple, "String").text = self.ref_loudness

    def set_rg_tags(self, rg_integrated, rg_range, rg_peak):
        if self.tags is None or self.tag is not None:
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
        if self.tag is None or self.tags is None:
            return
        xml.ElementTree(self.tags).write(path)
        self.tag = self.tags = None


class Mkvrg:
    def __init__(self, utils, thread=0):
        self.utils = utils
        self.thread = "Thread " + str(thread) + ":\t"
        self.xml_utils = XmlUtils(self.utils.ref_loudness)
        self.track_count = 0
        self.track = {}
        self.cur_path = self.rg_integrated = self.rg_range = self.rg_peak = ""
        self.mk_tmp = MakeTmpFile()
        self.tmp_file = self.mk_tmp.path

    def process_file(self, path):
        """Process a matroska file, analyzing it with bs1770gain and applying tags."""
        self.cur_path = path
        self.utils.log.info(self.thread + "Processing file: " + self.cur_path)
        self.__get_tracks()
        self.__process_tracks()
        self.utils.log.info(self.thread + "Finished processing file " + self.cur_path)

    def __get_tracks(self):
        """Get audio track numbers from bs1770gain"""
        buf = StringIO(self.utils.run_command("bs1770gain -l " + self.cur_path, subprocess.STDOUT,
                                              universal_newlines=True))
        self.tracks = {}
        i = 0
        for line in buf:
            if "Audio" in line and "Stream" in line:
                i += 1
                if self.utils.default_track == True and "default" not in line:
                    self.utils.log.info(self.thread + "Skipping non default audio track " + str(i) +
                                        ", you enabled --default (" + self.cur_path + ")")
                    continue
                matches = self.utils.track_list_regex.search(line)
                if not matches:
                    self.utils.log.warning(self.thread + "Problem finding track number for track " + str(i) +
                                           " (" + self.cur_path + ")")
                    continue
                self.tracks[i] = matches.group(1)

    def __process_tracks(self):
        if not self.tracks:
            self.utils.log.error(self.thread + "No audio tracks found in file (" + self.cur_path + ")")
            return False
        for tracknum, trackid in self.tracks.items():
            if not self.__get_bs1770gain_info(trackid):
                continue
            if not self.__write_xml_file():
                continue
            self.__apply_tags(trackid)
        self.utils.check_tags(self.cur_path, False)

    def __get_bs1770gain_info(self, trackid):
        buffer = StringIO(self.utils.run_command("bs1770gain --audio " + trackid + " -r " +
                                              ("-p " if self.utils.sample_peak else "-t ") + self.cur_path
                                              , subprocess.STDOUT, universal_newlines=True))
        if not buffer:
            self.utils.log.error(self.thread + "Problem running bs1770gain. (" + self.cur_path + ")")
            return False

        self.rg_integrated = self.rg_range = self.rg_peak = ""
        for line in buffer:
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
            self.utils.log.error(self.thread + "Could not find replaygain info from bs1770gain. (" +
                                 self.cur_path + ")")
            return False

        return True

    def __write_xml_file(self):
        """Write XML file with tags to temp file, for mkvpropedit."""
        self.mk_tmp.clear()
        self.xml_utils.set_rg_head()
        self.xml_utils.set_rg_tags(self.rg_integrated, self.rg_range, self.rg_peak)
        self.xml_utils.write_rg_xml(self.tmp_file)
        if os.path.getsize(self.tmp_file) == 0:
            self.utils.log.error(self.thread + "Could not write XML to temp file (" + self.cur_path + ")")
            return False
        return True

    def __apply_tags(self, trackid):
        """Apply replaygain tags with mkvpropedit."""
        if not self.utils.run_command("mkvpropedit --tags track:" + str(int(trackid) + 1) + ":" + self.tmp_file + " " +
                                      self.cur_path):
            self.utils.log.error(self.thread + "Problem applying replaygain tags to " + self.cur_path)
            return False
        return True

if __name__ == '__main__':
    main()
