#!/usr/bin/env python
import httplib, os.path, argparse, struct

"""
pdb_downloader.py
v0.1

Steeve Barbeau
@steevebarbeau
steeve-barbeau.blogspot.com

$ ./pdb.py --dll lsasrv.dll
Downloading file ...
Done"
Now   run `cabextract lsasrv.pd_` to extract PDB file from the CAB file

"""

url = "/download/symbols/%s.pdb/%s/%s.pd_"

def download_pdb(file_name, uuid):
  conn = httplib.HTTPConnection("msdl.microsoft.com")
  headers = {"User-Agent": "Microsoft-Symbol-Server/6.12.0002.633"}
  conn.request("GET", url % (file_name, uuid, file_name), "", headers)

  response = conn.getresponse()

  if response.status == 200:
    print "Downloading file ..."
    pdb_buffer = response.read()

    pdb_filename = os.path.basename(url % (file_name, uuid, file_name))
    pdb_file = open(pdb_filename, 'w')
    pdb_file.write(pdb_buffer)
    pdb_file.close()

    print """\tDone"
Now run `cabextract %s` to extract PDB file from the CAB file""" % pdb_filename
  else:
    print "FAIL"

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--file', dest='file', help='Filename')
  parser.add_argument('--uuid', dest='uuid', help='UUID')
  args = parser.parse_args()
  if args.file and args.uuid:
    download_pdb(os.path.splitext(os.path.basename(args.file))[0], uuid)
  else:
    parser.print_help()
