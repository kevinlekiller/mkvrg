#!/usr/bin/env python
"""Calculate Replaygain for all audio tracks in Matroska files and write the
appropriate track tags to said files"""
# pylint: disable=too-few-public-methods,too-many-instance-attributes

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

LOGLEVELS = {
    "all": 0,
    "debug": 10,
    "info": 20,
    "warning": 30,
    "error": 40,
    "critcial": 50,
    "silent": 99
}
# sort, so we get descending order of loglevels, just for the argparser choices
LOGLEVEL_NAMES = sorted(LOGLEVELS.keys(), key=LOGLEVELS.get, reverse=True)


def main():
    check_binaries()
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
        mkvrg = MatroskaFile(utils=utils, path=work, thread=thread)
        mkvrg.process_file()
        queue.task_done()


def check_binary(binary):
    """Check if a binary is in PATH."""
    result = True
    devnull = open(os.devnull, 'w')
    try:
        subprocess.call([binary], stdout=devnull, stderr=devnull)
    except OSError:
        result = False
    devnull.close()
    return result


def check_binaries():
    """Check if all required binaries are in PATH."""
    binaries = ["bs1770gain", "mkvpropedit", "mkvinfo"]
    for binary in binaries:
        if not check_binary(binary):
            print("ERROR: The program '" + binary + "' is required.")
            exit(1)


def run_command(command, stderr=None, universal_newlines=False):
    """Run a command in a shell, return the output as a string."""
    ret = ""
    try:
        ret = str(subprocess.check_output(shlex.split(command), stderr=stderr,
                                          universal_newlines=universal_newlines))
    except subprocess.CalledProcessError:
        pass
    except OSError:
        pass
    return ret


def get_ref_loudness():
    """Get default replaygain reference loudness from bs1770gain."""
    buf = run_command("bs1770gain --help", stderr=subprocess.STDOUT)
    if not buf:
        return False
    buf = re.search(r"\(([-\d.]+\s+LUFS), default\)", buf)
    if "LUFS" not in buf.group(1):
        return False
    return buf.group(1)


class Log(object):
    def __init__(self, loglevel=20, name="mkvrg"):
        """"""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(loglevel)
        if not len(self.logger.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s [%(levelname)s]:\t%(message)s'))
            handler.setLevel(loglevel)
            self.logger.addHandler(handler)
        self.exit = False

    def set_level(self, loglevel):
        self.logger.setLevel(loglevel)

    def log(self, message):
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

    def __do_exit(self, code=1):
        if self.exit:
            print("The --exit option is enabled, exiting.")
            exit(code)


class ThreadMkvrg(object):
    def __init__(self, utils):
        threads = utils.threads
        total_work = len(utils.files)
        if total_work < threads:
            threads = total_work

        # pylint: disable=E1101
        queue = multiprocessing.JoinableQueue(threads)
        # pylint: enable=E1101

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


class CheckArgs(object):
    def __init__(self, utils):
        self.utils = utils
        args = self.__parse_args()
        self.utils.log.exit = self.utils.exit
        self.utils.log.set_level(self.utils.loglevel)
        self.utils.ref_loudness = get_ref_loudness()
        if self.utils.ref_loudness == "":
            self.utils.log("Could not find reference replaygain loudness from bs1770gain.")
            exit(1)

        for arg in args:
            if os.path.isdir(arg):
                self.__check_dir(arg)
            else:
                self.__check_file(arg)

    def __parse_args(self):
        """Parse command line arguments."""
        parser = ArgumentParser()
        parser.add_argument(
            "-s", "--samplepeak", help="Use the sample peak option instead of true" +
            " peak for bs1770gain, this is much faster.", action="store_true")
        parser.add_argument(
            "-t", "--threads", type=int, help="Amount of threads to use to process files.",
            default=1)
        parser.add_argument(
            "-d", "--default", help="Only process the default audio track?", action="store_true")
        parser.add_argument(
            "-m", "--minsize", type=int, help="Minimum size of matroska file in bytes.", default=0)
        parser.add_argument(
            "-c", "--verify",
            help="Verify if matroska file has replaygain tags before and after analyzing.",
            action="store_true")
        parser.add_argument(
            "-f", "--force",
            help="Force scanning files for replaygain, even if they already have replaygain tags.",
            action="store_true")
        parser.add_argument(
            "-e", "--exit", help="Stop and exit if any problems are encountered.",
            action="store_true")
        parser.add_argument(
            "-v", "--loglevel", type=str,
            help="Level of loglevel. (20 = info (default), 99 = silent, 10 = debug, " +
            "30 = warning, 40 = error, 50 = critical, 0 = all).", default="info",
            choices=LOGLEVEL_NAMES)
        parser.add_argument(
            "paths",
            help="Path(s) to folder(s) or file(s) to scan matroska files for replaygain info.",
            nargs="*")
        args = parser.parse_args()
        self.utils.loglevel = LOGLEVELS[args.loglevel]
        self.utils.sample_peak = args.samplepeak
        self.utils.default_track = args.default
        self.utils.exit = args.exit
        self.utils.force = args.force

        self.utils.threads = args.threads
        if self.utils.threads == 0:
            self.utils.threads = multiprocessing.cpu_count()
        if self.utils.threads < 0:
            self.utils.log.warning("The --threads must be at least 0")
            self.utils.log.warning("Setting --threads to 1")
            self.utils.threads = 1

        self.utils.minsize = args.minsize
        if self.utils.minsize < 0:
            self.utils.log.error("The --minsize value must be a positive number.")
            self.utils.log.info("Setting --minsize to 0")
            self.utils.minsize = 0

        self.utils.verify = args.verify
        if self.utils.verify and not check_binary("mediainfo"):
            self.utils.log.error(
                "You enabled the --verify option but you do not have mediainfo installed.")
            self.utils.log.info("Setting --verify to false.")
            self.utils.verify = False

        if not args.paths:
            self.utils.log.info(
                "No path(s) given, processing current working directory recursively.")
            return ["."]
        return args.paths

    def __check_file(self, path):
        try:
            candidate = MatroskaFile(path=path, utils=self.utils)
            self.utils.files.append(candidate.get_path())
        except ValueError as error:
            self.utils.log.info("Path '{}' does not point to a file of interest: {}."
                                .format(path, error))

    def __check_dir(self, directory):
        for rootdir, _, filenames in os.walk(directory):
            files = fnmatch.filter(filenames, '*.[mM][kK][aAvV]')
            files.extend(fnmatch.filter(filenames, '*.[mM][kK]3[dD]'))
            for filename in files:
                self.__check_file(os.path.join(rootdir, filename))


class Utils(object):
    def __init__(self):
        self.opt_exit = ""
        self.exit = self.minsize = self.threads = 0
        # self.loglevel = LOGLEVELS["info"]
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
        if "ITU-R BS.1770" in run_command("mediainfo " + path +
                                          ' --Inform="Audio;%REPLAYGAIN_ALGORITHM%"'):
            if first_check:
                self.log.info("Replaygain tags found in file (" + path + "), skipping.")
                return False
            return True
        if first_check:
            self.log.info("No replaygain tags found in file (" + path + ") continuing.")
            return True

        self.log.error(
            "No replaygain tags were found in file (" +
            path + ") after applying with mkvpropedit.")
        return False


class MakeTmpFile(object):
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


class XmlUtils(object):
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


class Mkvrg(object):
    def __init__(self, utils, thread=0, **kwds):
        # Strictly, len(**kwds) should now be 0, but if not we might have forgot something.
        super(Mkvrg, self).__init__(**kwds)
        self.utils = utils
        self.s_thread = "Thread " + str(thread) + ":\t"
        self.xml_utils = XmlUtils(self.utils.ref_loudness)
        self.track_count = 0
        self.track = {}
        self.rg_integrated = self.rg_range = self.rg_peak = ""
        self.mk_tmp = MakeTmpFile()
        self.tmp_file = self.mk_tmp.path
        self.tracks = {}

    def get_tracks(self, path):
        """Get audio track numbers from bs1770gain"""
        buf = StringIO(run_command("bs1770gain -l " + path, subprocess.STDOUT,
                                   universal_newlines=True))
        i = 0
        for line in buf:
            if "Audio" in line and "Stream" in line:
                i += 1
                if self.utils.default_track is True and "default" not in line:
                    self.utils.log.info(
                        self.s_thread + "Skipping non default audio track " + str(i) +
                        ", you enabled --default (" + path + ")")
                    continue
                matches = self.utils.track_list_regex.search(line)
                if not matches:
                    self.utils.log.warning(
                        self.s_thread + "Problem finding track number for track " + str(i) +
                        " (" + path + ")")
                    continue
                self.tracks[i] = matches.group(1)


class MkxFile(Mkvrg):
    def __init__(self, path, **kwds):
        if os.path.isfile(path):
            self.__path = path
        else:
            raise ValueError("Path '{}' does not point to a file".format(path))
        # !!! Don't be tempted to call
        # super(self.__class__, self).__init__(utils), it is not
        # quite the same!!! Looks like some level of redundancy is left in Python 2.7 at least.
        super(MkxFile, self).__init__(**kwds)

    def get_path(self):
        return self.__path

    def ismatroska(self):
        """Check if file is an actual matroska file and is of size 'minsize'"""
        path = self.__path
        self.utils.log.info("Checking file (" + path + ").")
        if self.utils.minsize > 0 and os.path.getsize(path) < self.utils.minsize:
            self.utils.log.info("The file is smaller than your --minsize setting, skipping.")
            return False
        handle = open(path)
        data = handle.read(64)
        handle.close()
        if not (data.startswith("\x1a\x45\xdf\xa3") and "matroska" in data):
            self.utils.log.debug("File does not seem to contain Matroska data.")
            return False
        return True

    def hasrgtags(self, path, first_check=True):
        """Check if matroska file has replaygain tags."""
        if not self.utils.verify:
            return True
        if first_check and self.utils.force:
            self.utils.log.info("Skipping replaygain tags check, --force is on.")
            return True
        if "ITU-R BS.1770" in run_command("mediainfo " + path +
                                          ' --Inform="Audio;%REPLAYGAIN_ALGORITHM%"'):
            if first_check:
                self.utils.log.info("Replaygain tags found in file (" + path + "), skipping.")
                return False
            return True
        if first_check:
            self.utils.log.info("No replaygain tags found in file (" + path + ") continuing.")
            return True

        self.utils.log.error(
            "No replaygain tags were found in file (" +
            path + ") after applying with mkvpropedit.")
        return False


class MatroskaFile(MkxFile):
    """
    Objects of this class are guaranteed to be of file type matroska AND to have audio tracks.
    If one tries to instantiate this class and the above conditions are not met an exception will
    be raised.
    """

    def __init__(self, **kwds):
        # !!! Don't be tempted to call
        # super(self.__class__, self).__init__(path, utils), it is not
        # quite the same!!! Looks like some level of redundancy is left in Python 2.7 at least.
        super(MatroskaFile, self).__init__(**kwds)

        # this should also take care of initializing self.tracks
        if not self.ismatroska():
            raise ValueError("No matroska data found")
        elif not self.has_audio():
            raise ValueError("No audio")

    def __get_bs1770gain_info(self, trackid):
        buffer_ = StringIO(
            run_command(
                "bs1770gain --audio {trackid} -r {opt_peak_algo} {path}"
                .format(
                    trackid=trackid,
                    opt_peak_algo="-p " if self.utils.sample_peak else "-t ",
                    path=self.get_path()
                ),
                subprocess.STDOUT, universal_newlines=True
            )
        )
        if not buffer_:
            self.utils.log.error(
                self.s_thread + "Problem running bs1770gain. (" + self.get_path() + ")")
            return False

        self.rg_integrated = self.rg_range = self.rg_peak = ""
        for line in buffer_:
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
            self.utils.log.error(
                self.s_thread + "Could not find replaygain info from bs1770gain. (" +
                self.get_path() + ")")
            return False

        return True

    def __process_tracks(self):
        if not self.tracks:
            self.utils.log.error(
                self.s_thread + "No audio tracks found in file (" + self.get_path() + ")")
            return False
        for trackid in self.tracks.values():
            if not self.__get_bs1770gain_info(trackid):
                continue
            if not self.__write_xml_file(self.get_path()):
                continue
            self.__apply_tags(trackid, self.get_path())
        self.utils.check_tags(self.get_path(), False)

    def __write_xml_file(self, path):
        """Write XML file with tags to temp file, for mkvpropedit."""
        self.mk_tmp.clear()
        self.xml_utils.set_rg_head()
        self.xml_utils.set_rg_tags(self.rg_integrated, self.rg_range, self.rg_peak)
        self.xml_utils.write_rg_xml(self.tmp_file)
        if os.path.getsize(self.tmp_file) == 0:
            self.utils.log.error(
                self.s_thread + "Could not write XML to temp file (" + path + ")")
            return False
        return True

    def __apply_tags(self, trackid, path):
        """Apply replaygain tags with mkvpropedit."""
        if not run_command("mkvpropedit --tags track:" + str(int(trackid) + 1) +
                           ":" + self.tmp_file + " " + path):
            self.utils.log.error(
                self.s_thread + "Problem applying replaygain tags to " + path)
            return False
        return True

    def process_file(self):
        """Process a matroska file, analyzing it with bs1770gain and applying tags."""
        self.utils.log.info(self.s_thread + "Processing file: " + self.get_path())
        self.get_tracks(self.get_path())
        self.__process_tracks()
        self.utils.log.info(self.s_thread + "Finished processing file " + self.get_path())

    def has_audio(self):
        # initialize self.tracks simply by checking if file has audio
        if not self.tracks:
            self.get_tracks(self.get_path())
        return True if self.tracks else False


class MatroskaAudioTrack(MatroskaFile):
    def __init__(self):
        MatroskaFile.__init__(self)
        self.track_id = 0
        print(super.path)


if __name__ == '__main__':
    main()
