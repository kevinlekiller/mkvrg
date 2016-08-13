#!/usr/bin/env python

import sys
import os
from glob import glob
import fnmatch
# Need to install magic for checking if file is matroska (sudo pip install filemagic)
#import magic


def main(argv):
    if len(argv) == 1:
        return 1
    return parse_args(argv[1:])


def parse_args(args):
    path = os.path
    for arg in args:
        if path.isdir(arg):
            return process_dir(arg),
        elif path.isfile(arg):
            return process_file(arg)
    return 1


def process_dir(directory):
    for rootdir, dirnames, filenames in os.walk(directory):
        for filename in fnmatch.filter(filenames, '*.mkv'):
            process_file(os.path.join(rootdir, filename))

def process_file(path):
    print(path)


if __name__ == '__main__':
    main(sys.argv)