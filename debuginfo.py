#!/usr/bin/env python3

# Look for debuginfo package tarfiles in a Cygwin releasearea mirror.  If they
# haven't been seen before, extract .dbg files, convert to .sym
#

from __future__ import print_function
import argparse
import os
import re
import shutil
import tarfile
import tempfile

# XXX: We could process all debuginfo files, but for the moment, just consider
# the subset we are interested in
interesting = ['cygwin-debuginfo', 'xorg-server-debuginfo']


def main(args):
    for arch in ['x86', 'x86_64']:
        basedir = os.path.join(args.rel_area, arch, 'release')
        for (dirpath, subdirs, files) in os.walk(basedir):
            if any(map(lambda i: dirpath.endswith(i), interesting)):
                for f in files:
                    if re.search(r'\.tar\.(bz2|gz|lzma|xz)$', f):
                        process(args, os.path.join(dirpath, f))


def process(args, f):
    print(f)

    # extract .dbg files from tarfile into a temporary directory
    tempdir = tempfile.mkdtemp()

    with tarfile.open(f) as tf:
        dbgmembers = [m for m in tf.getmembers() if m.name.endswith('.dbg')]
        tf.extractall(tempdir, dbgmembers)

        # install symbols
        for dbgfile in dbgmembers:
            install_symbols(args, os.path.join(tempdir, dbgfile.name))

    # remove tempdir to cleanup
    shutil.rmtree(tempdir)


# XXX: need to remember fileid/buildid we have seen, and what package the came
# from.
# then we don't need to consider packages we have seen already
# and can answer questions about what package a given buildid comes from
#

def install_symbols(args, f):
    # print(f)

    with tempfile.NamedTemporaryFile(delete=False) as t:
        # print(t.name)

        if f.endswith('.dbg'):
            # A .dbg file, detached debug information PECOFF file
            # use dump_syms to create .sym file

            os.system('breakpad_dump_syms ' + f + ' >' + t.name)
            (buildid, fileid) = extract_sym_ids(t.name)
            # print("buildid %s fileid %s" % (buildid, fileid))

            # cygwin1.dbg is irregularly named
            # as a special case, treat it as if it was named cygwin1.dll.dbg
            if fileid == 'cygwin1.dbg':
                fileid = 'cygwin1.dll.dbg'

            # remove .dbg extension
            fileid = os.path.splitext(fileid)[0]

            # replace .dbg extension with .sym
            symfile = fileid + '.sym'

        elif f.endswith('.sym'):
            # Already a breakpad .sym file

            # d2u it in case it came from a Windows .sym file generation tool
            os.system('d2u -n ' + f + ' ' + t.name)
            (buildid, fileid) = extract_sym_ids(t.name)

            # replace .pdb extension with .sym
            symfile = os.path.splitext(fileid)[0] + '.sym'

        else:
            print('Unknown file type %s' % (f))

        # ensure the needed directory exists
        symbolpath = os.path.join(args.symbol_root, fileid, buildid)
        os.makedirs(symbolpath, exist_ok=True)

        # install the .sym file
        os.rename(t.name, os.path.join(symbolpath, symfile))
        print('%s installed to %s' % (symfile, symbolpath))


# extract the 'id' and 'name' fields from the MODULE record at the start of a
# .sym file
def extract_sym_ids(fn):
    with open(fn) as f:
        return tuple(f.readline().split()[3:5])


if __name__ == "__main__":
    rel_area_default = "/var/ftp/pub/cygwin"
    symbol_root_default = "/crashprocessor/symbols"

    parser = argparse.ArgumentParser(description='Process Cygwin debuginfo packages')
    parser.add_argument('--releasearea', action='store', metavar='DIR', help="release directory (default: " + rel_area_default + ")", default=rel_area_default, dest='rel_area')
    parser.add_argument('--symbolroot', action='store', metavar='DIR', help="symbol root (default: " + symbol_root_default + ")", default=symbol_root_default, dest='symbol_root')
    (args) = parser.parse_args()

    main(args)
