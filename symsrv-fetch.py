#!/usr/bin/env python
#
# This script will read a CSV of modules from fetchlist.txt, and tries to
# retrieve missing symbols from Microsoft's symbol server. It honours a
# blacklist (blacklist.txt) of symbols that are known to be from our
# applications.
#
# You must have 'pdb_fetch' (which requires 'cabextract') and
# 'dump_syms' available in PATH.

from __future__ import with_statement
import sys
import os
import time, datetime
import subprocess
import StringIO
import shutil
import ctypes
import logging
from collections import defaultdict
from tempfile import mkdtemp

# Temporary directory to store symbols in locally
temp_dir='temp'
# Path to store symbols in
symbol_path='symbols'
# Path to store pdbs in
pdb_path='pdb'

thisdir = os.path.dirname(__file__)

verbose = False
if len(sys.argv) > 1 and sys.argv[1] == "-v":
  verbose = True
  sys.argv.pop(1)

log = logging.getLogger()
log.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt="%(asctime)-15s %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
filelog = logging.FileHandler(filename=os.path.join(thisdir,
                                                    "symsrv-fetch.log"))
filelog.setLevel(logging.INFO)
filelog.setFormatter(formatter)
log.addHandler(filelog)

if verbose:
  handler = logging.StreamHandler()
  handler.setLevel(logging.DEBUG)
  handler.setFormatter(formatter)
  log.addHandler(handler)
  verboselog = logging.FileHandler(filename=os.path.join(thisdir,
                                                      "verbose.log"))
  log.addHandler(verboselog)

log.info("Started")

# Symbols that we know belong to us, so don't ask Microsoft for them.
blacklist=set()
try:
  bf = file(os.path.join(thisdir, 'blacklist.txt'), 'r')
  for line in bf:
      blacklist.add(line.strip().lower())
  bf.close()
except IOError:
  pass
log.debug("Blacklist contains %d items" % len(blacklist))

modules = defaultdict(set)
modulescount = 0
log.debug("Loading fetchlist...")
try:
  mf = file(os.path.join(thisdir, 'fetchlist.txt'), 'r')
  for line in mf:
    line = line.rstrip()
    bits = line.split(',')
    if len(bits) < 2:
      continue
    pdb, uuid = bits[:2]
    if pdb and pdb.endswith('.pdb') and uuid and uuid != "000000000000000000000000000000000":
      log.debug("%s %s" % (pdb, uuid))
      modules[pdb].add(uuid)
      modulescount += 1
    else:
      log.debug("%s/%s not a PDB or no UUID" % (pdb, uuid))
except:
  log.exception("Error reading fetch list")
  sys.exit(1)
log.debug("Fetchlist contains %d items" % modulescount)

log.debug("Fetching symbols")
total = sum(len(ids) for ids in modules.values())
current = 0
blacklist_count = 0
existing_count = 0
not_found_count = 0
conversion_failed = 0
converted_count = 0

# Now try to fetch all the unknown modules from the symbol server
for filename, ids in modules.iteritems():
  # Sometimes we get non-ascii in here. This is definitely not
  # correct, but it should at least stop us from throwing.
  filename = filename.encode('ascii', 'replace')

  if filename.lower() in blacklist:
    log.debug("%s on blacklist", filename)
    current += len(ids)
    blacklist_count += len(ids)
    continue

  for id in ids:
    current += 1
    if verbose:
      sys.stdout.write("[%6d/%6d] %3d%% %s\n" % (current, total,
                                                 int(100 * current / total),
                                                 filename))

    sym_file = os.path.join(symbol_path, filename, id,
                            filename.replace(".pdb","") + ".sym")

    if os.path.exists(sym_file):
      # We already have this symbol
      log.debug("%s/%s already present", filename, id)
      existing_count += 1
      continue

    # Not in the blacklist, and we don't already have it, so ask the symbol
    # server for it.
    pdb_downloader = os.path.join(thisdir, ".", "pdb_fetch")
    proc = subprocess.Popen([pdb_downloader,
                             "--file", filename,
                             "--uuid", id,
                             "--cache", pdb_path],
                            stdout = subprocess.PIPE,
                            stderr = subprocess.PIPE)

    (stdoutdata, stderrdata) = proc.communicate()

    convert_output = stderrdata.strip()
    log.debug("pdb_fetch output: '%s'", convert_output)

    if proc.returncode != 0:
      not_found_count += 1
      log.debug("pdb_fetch failed for %s/%s %d", filename, id, proc.returncode)
      continue

    log.debug("Successfully fetched %s/%s", filename, id)

    pdb_file = stdoutdata.strip()
    log.debug("pdb_fetch output: '%s'", pdb_file)

    if not os.path.exists(os.path.join(symbol_path, filename, id)):
      os.makedirs(os.path.join(symbol_path, filename, id))
    if os.system("/wip/dump_syms/dump_syms %s >%s" % (pdb_file, sym_file)) != 0:
      os.remove(sym_file)
      log.debug("Failed to convert %s/%s", filename, id)
      conversion_failed = +1

    if os.path.exists(sym_file):
      log.debug("Successfully converted %s/%s", filename, id)
      converted_count += 1

if verbose:
  sys.stdout.write("\n")

log.info("%d considered, %d already present, %d in blacklist, %d not found, %d conversion failed"
         % (total, existing_count, blacklist_count, not_found_count, conversion_failed))

log.info("Converted and installed %d symbol files" % converted_count)
log.info("Finished, exiting")
