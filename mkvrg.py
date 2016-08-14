#!/usr/bin/env python

import sys
import os
import fnmatch
import magic
from argparse import ArgumentParser


def main(argv):
    mkvrg = Mkvrg("mkvrg")
    return mkvrg.start(parse_args(mkvrg))


def parse_args(mkvrg):
    parser = ArgumentParser()
    parser.add_argument("-m", "--minsize", type=int, help="Minimum size of matroska file in MB")
    parser.add_argument("-c", "--verify", help="Verify if matroska file has replaygain tags before and after analyzing.", action="store_true")
    parser.add_argument("-f", "--force", help="Force scanning files for replaygain, even if they already have replaygain tags.", action="store_true")
    parser.add_argument("paths", help="Path(s) to folder(s) or file(s) to scan matroska files for replaygain info.", nargs="*")
    args = parser.parse_args()
    if args.force:
        mkvrg.force = True
    if args.verify:
        mkvrg.verify = True
    if args.minsize > 0:
        mkvrg.minsize = args.minsize
    if not args.paths:
        print("No path(s) given, processing current working directory recursively.")
        return ["."]
    return args.paths


class Mkvrg:
    def __init__(self, name):
        self.name = name
        self.force = False
        self.minsize = 0
        self.verify = False

    def start(self, args):
        path = os.path
        for arg in args:
            if path.isdir(arg):
                self.process_dir(arg),
            elif path.isfile(arg):
                self.process_file(arg)
            else:
                print("This does not look like a valid path: " + arg)

    def process_dir(self, directory):
        for rootdir, dirnames, filenames in os.walk(directory):
            files = fnmatch.filter(filenames, '*.[mM][kK][aAvV]')
            files.extend(fnmatch.filter(filenames, '*.[mM][kK]3[dD]'))
            for filename in files:
                self.process_file(os.path.join(rootdir, filename))

    def process_file(self, path):
        print(path)
        if not self.test_matroska(path):
            return

    @staticmethod
    def test_matroska(path):
        with magic.Magic() as m:
            if "matroska" in m.id_filename(path).lower():
                return True
        print("File is not matroska.")
        return False

if __name__ == '__main__':
    main(sys.argv)
