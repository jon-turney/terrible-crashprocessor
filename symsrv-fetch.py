#!/usr/bin/env python
#
# This script will read a CSV of modules from fetchlist.txt, and tries to
# retrieve missing symbols from Microsoft's symbol server. It honours a
# blacklist (blacklist.txt) of symbols that are known to be from our
# applications, and it maintains it's own list of symbols that the MS symbol
# server doesn't have (skiplist.txt).
#
# The script must have installed alongside it:
# * pdb_downloader.py
#
# The script also depends on having write access to the directory it is
# installed in, to write the skiplist text file.
#
# Finally, you must have 'dump_syms' and 'cabextract' available in %PATH%.

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

def write_skiplist():
  try:
    with open(os.path.join(thisdir, 'skiplist.txt'), 'w') as sf:
      for (debug_id,debug_file) in skiplist.iteritems():
          sf.write("%s %s\n" % (debug_id, debug_file))
  except IOError:
    log.exception("Error writing skiplist.txt")

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

# Symbols that we've asked for in the past unsuccessfully
skiplist={}
skipcount = 0
try:
  sf = file(os.path.join(thisdir, 'skiplist.txt'), 'r')
  for line in sf:
      line = line.strip()
      if line == '':
          continue
      s = line.split(None, 1)
      if len(s) != 2:
        continue
      (debug_id, debug_file) = s
      skiplist[debug_id] = debug_file.lower()
      skipcount += 1
  sf.close()
except IOError:
  pass
log.debug("Skiplist contains %d items" % skipcount)

modules = defaultdict(set)
modulescount = 0
log.debug("Loading module list...")
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
skiplist_count = 0
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
    if id in skiplist and skiplist[id] == filename.lower():
      # We've asked the symbol server previously about this, so skip it.
      log.debug("%s/%s already in skiplist", filename, id)
      skiplist_count += 1
      continue

    sym_file = os.path.join(symbol_path, filename, id,
                            filename.replace(".pdb","") + ".sym")
    pdb_file = os.path.join(pdb_path, filename, id, filename)

    if os.path.exists(sym_file):
      # We already have this symbol
      log.debug("%s/%s already present", filename, id)
      existing_count += 1
      continue

    # Not in the blacklist, skiplist, and we don't already have it, so
    # ask the symbol server for it.
    pdb_downloader = os.path.join(thisdir, ".", "pdb_downloader.py")
    proc = subprocess.Popen([pdb_downloader,
                             "--file", filename,
                             "--uuid", id],
                            stdout = subprocess.PIPE,
                            stderr = subprocess.STDOUT)
    # kind of lame, want to prevent it from running too long
    start = time.time()
    # 30 seconds should be more than enough time
    while proc.poll() is None and (time.time() - start) < 30:
      time.sleep(1)
    if proc.poll() is None:
      # kill it, it's been too long
      log.debug("Timed out downloading %s/%s", filename, id)
      ctypes.windll.kernel32.TerminateProcess(int(proc._handle), -1)
    elif proc.returncode != 0:
      not_found_count += 1
      # Don't skiplist this symbol if we've previously downloaded
      # other symbol versions for the same file. It's likely we'll
      # be able to download it at some point
      if not (os.path.exists(os.path.join(symbol_path, filename))):
        log.debug("Couldn't fetch %s/%s, adding to skiplist", filename, id)
        skiplist[id] = filename
      else:
        log.debug("Couldn't fetch %s/%s, but not skiplisting", filename, id)
      convert_output = proc.stdout.read().strip()
      log.debug("pdb_downloader output: '%s'", convert_output)

    if not os.path.exists(filename):
      log.debug("Failed to download %s/%s", filename, id)
      continue

    log.debug("Successfully downloaded %s/%s", filename, id)

    if not os.path.exists(os.path.join(pdb_path, filename, id)):
      os.makedirs(os.path.join(pdb_path, filename, id))
    shutil.move(filename, pdb_file)

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

log.info("%d considered, %d already present, %d in blacklist, %d skipped, %d not found, %d conversion failed"
         % (total, existing_count, blacklist_count, skiplist_count, not_found_count, conversion_failed))

# Write out our new skip list
write_skiplist()

log.info("Converted and installed %d symbol files" % converted_count)
log.info("Finished, exiting")
