#!/usr/bin/env python

import sys
import os
import fnmatch
import magic


def main(argv):
    mkvrg = Mkvrg("mkvrg")
    paths = argv[1:]
    if not len(paths):
        paths = ["."]
        print "No arguments given, processing current working directory recursively."

    return mkvrg.start(paths)


class Mkvrg:
    def __init__(self, name):
        self.name = name

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
            for filename in fnmatch.filter(filenames, '*.mkv'):
                self.process_file(os.path.join(rootdir, filename))

    def process_file(self, path):
        print(path)
        if not self.test_matroska(path):
            return

    @staticmethod
    def test_matroska(path):
        with magic.Magic() as m:
            if "matroska" not in m.id_filename(path).lower():
                print("File is not matroska.")
                return False
        return True

if __name__ == '__main__':
    main(sys.argv)
