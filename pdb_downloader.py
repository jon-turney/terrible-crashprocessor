#!/usr/bin/env python
import httplib, os.path, argparse, sys

"""
pdb_downloader.py

Based on https://gist.github.com/steeve85/2665503 by Steeve Barbeau

"""

url = "/download/symbols/%s.pdb/%s/%s.pd_"

def download_pdb(file_name, uuid):
  conn = httplib.HTTPConnection("msdl.microsoft.com")
  headers = {"User-Agent": "Microsoft-Symbol-Server/6.12.0002.633"}
  conn.request("GET", url % (file_name, uuid, file_name), "", headers)

  response = conn.getresponse()

  if response.status != 200:
    print "Fetching from symbol server failed"
    return 1

  print "Downloading file ..."
  pdb_buffer = response.read()

  pdb_filename = os.path.basename(url % (file_name, uuid, file_name))
  pdb_file = open(pdb_filename, 'w')
  pdb_file.write(pdb_buffer)
  pdb_file.close()

  print "Downloaded"

  # Now run cabextract to extract PDB file from the CAB file
  status = os.system("cabextract -q %s" % (pdb_filename))
  if status != 0:
    print "Decompressing cabinet failed"
    return 1

  print "Extracted"
  os.remove(pdb_filename)
  return 0

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--file', dest='file', help='Filename')
  parser.add_argument('--uuid', dest='uuid', help='UUID')
  args = parser.parse_args()
  if args.file and args.uuid:
    return download_pdb(os.path.splitext(os.path.basename(args.file))[0], args.uuid)
  else:
    parser.print_help()
  return 0

if __name__ == "__main__":
  sys.exit(main())
