#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import json
import hashlib
import sys
import os
from optparse import OptionParser
import wget

__version__ = '1.0.0'
__title__ = 'zenodo_get'
__summary__ = 'Zenodo record downloader.'
__uri__ = 'https://github.com/dvolgyes/zenodo_get'
__license__ = 'AGPL v3'
__author__ = 'David Völgyes'
__email__ = 'david.volgyes@ieee.org'
__description__ = """
This program is meant to download a Zenodo record using DOI or record ID.
"""


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def check_hash(filename, checksum):
    algorithm, value = checksum.split(':')
    h = hashlib.new(algorithm)
    with open(filename, 'rb') as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            h.update(data)
    digest = h.hexdigest()
    return value, digest


if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option('-r', '--record',
                      action='store',
                      type='string',
                      dest='record',
                      help='Zenodo record ID',
                      default=None)

    parser.add_option('-d', '--doi',
                      action='store',
                      type='string',
                      dest='doi',
                      help='Zenodo DOI',
                      default=None)

    parser.add_option('-e', '--continue-on-error',
                      action='store_true',
                      dest='error',
                      help='Continue with next file if error happens.',
                      default=False)

    parser.add_option('-k', '--keep',
                      action='store_true',
                      dest='keep',
                      help='Keep files with invalid checksum.',
                      default=False)

    (options, args) = parser.parse_args()

    if len(args) > 0:
        try:
            t = int(args[0])
            options.record = args[0]
        except ValueError:
            options.doi = args[0]
    elif options.doi is None and options.record is None:
        parser.print_help()
        sys.exit(0)

    if options.doi is not None:
        url = options.doi
        if not url.startswith('http'):
            url = f'https://doi.org/{url}'
        r = requests.get(url)
        if not r.ok:
            eprint('DOI could not be resolved. Try again, or use record ID.')
            sys.exit(1)
        recordID = r.url.split('/')[-1]
    else:
        recordID = options.record
    recordID = recordID.strip()

    url = 'https://zenodo.org/api/records/'
    r = requests.get(url+recordID)
    if r.ok:
        js = json.loads(r.text)
        files = js['files']
        total_size = sum(f['size'] for f in files)
        eprint(f'Total size: {total_size/2**20:.1f} MB')
        for f in files:
            link = f['links']['self']
            size = f['size']/2**20
            eprint(f'Link: {link}   size: {size:.1f}MB')
            filename = wget.download(link)
            eprint()
            checksum = f['checksum']
            h1, h2 = check_hash(filename, checksum)
            if h1 == h2:
                eprint(f'Checksum is correct. ({h1})')
            else:
                eprint(f'Checksum is INCORRECT! expected: {h1} got:{h2})')
                if not options.keep:
                    eprint('  File is deleted.')
                    os.remove(filename)
                else:
                    eprint('  File is NOT deleted!')
                if not options.error:
                    sys.exit(1)
        eprint('All files have been downloaded.')
    else:
        eprint('Record could not get accessed.')
        sys.exit(1)
