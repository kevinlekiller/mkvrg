#!/usr/bin/env python

import sys
import os
import fnmatch
import magic


def main(argv):
    if len(argv) == 1:
        print("At least 1 argument is required, files or folders.")
        return 1

    mkvrg = Mkvrg("mkvrg")
    return mkvrg.start(argv[1:])


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


    def test_matroska(self, path):
        with magic.Magic() as m:
            if "matroska" not in m.id_filename(path).lower():
                print("File is not matroska.")
                return False
        return True

if __name__ == '__main__':
    main(sys.argv)