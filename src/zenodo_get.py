#!/usr/bin/env python3
import requests
import json
import hashlib
import sys
import os
from optparse import OptionParser
import wget
import time
import signal

__version__ = '1.2.1'
__title__ = 'zenodo_get'
__summary__ = 'Zenodo_get - a downloader for Zenodo records'
__uri__ = 'https://gitlab.com/dvolgyes/zenodo_get'
__license__ = 'AGPL v3'
__author__ = 'David Völgyes'
__email__ = 'david.volgyes@ieee.org'
__doi__ = '10.5281/zenodo.1261812'
__description__ = """
This program is meant to download complete Zenodo records based
on the Zenodo record ID or the DOI. The primary goal is to ease access
to large records with dozens of files.
"""
__bibtex__ = (
    """@misc{david_volgyes_2018_"""
    + __doi__
    + """,
  author  = {David Völgyes},
  title   = {Zenodo_get: a downloader for Zenodo records.},
  month   = june,
  year    = 2018,
  doi     = {"""
    + __doi__
    + """},
  url     = {https://doi.org/"""
    + __doi__
    + """}
}"""
)
__reference__ = (
    """David Völgyes. (2018, June 4). \
Zenodo_get: a downloader for Zenodo records (Version """
    + __version__
    + """).
Zenodo. https://doi.org/"""
    + __doi__
)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def ctrl_c(func):
    signal.signal(signal.SIGINT, func)
    return func


abort_signal = False
abort_counter = 0


@ctrl_c
def handle_ctrl_c(*args, **kwargs):
    global abort_signal
    global abort_counter

    abort_signal = True
    abort_counter += 1

    if abort_counter >= 2:
        eprint()
        eprint('Immediate abort. There might be unfinished files.')
        sys.exit(1)


def check_hash(filename, checksum):
    algorithm, value = checksum.split(':')
    if not os.path.exists(filename):
        return value, 'invalid'
    h = hashlib.new(algorithm)
    with open(filename, 'rb') as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            h.update(data)
    digest = h.hexdigest()
    return value, digest


def zenodo_get(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = OptionParser(
        usage='%prog [options] RECORD_OR_DOI', version=f'%prog {__version__}'
    )

    parser.add_option(
        '-c',
        '--cite',
        dest='cite',
        action='store_true',
        default=False,
        help='print citation information',
    )

    parser.add_option(
        '-r',
        '--record',
        action='store',
        type='string',
        dest='record',
        help='Zenodo record ID',
        default=None,
    )

    parser.add_option(
        '-d',
        '--doi',
        action='store',
        type='string',
        dest='doi',
        help='Zenodo DOI',
        default=None,
    )

    parser.add_option(
        '-m',
        '--md5',
        action='store_true',
        # ~type=bool,
        dest='md5',
        help='Create md5sums.txt for verification.',
        default=False,
    )

    parser.add_option(
        '-w',
        '--wget',
        action='store',
        type='string',
        dest='wget',
        help='Create URL list for download managers. '
        '(Files will not be downloaded.)',
        default=None,
    )

    parser.add_option(
        '-e',
        '--continue-on-error',
        action='store_true',
        dest='error',
        help='Continue with next file if error happens.',
        default=False,
    )

    parser.add_option(
        '-k',
        '--keep',
        action='store_true',
        dest='keep',
        help='Keep files with invalid checksum.' ' (Default: delete them.)',
        default=False,
    )

    parser.add_option(
        '-n',
        '--do-not-continue',
        action='store_false',
        dest='cont',
        help='Do not continue previous download attempt. (Default: continue.)',
        default=True,
    )

    parser.add_option(
        '-R',
        '--retry',
        action='store',
        type=int,
        dest='retry',
        help='Retry on error N more times.',
        default=0,
    )

    parser.add_option(
        '-p',
        '--pause',
        action='store',
        type=float,
        dest='pause',
        help='Wait N second before retry attempt, e.g. 0.5',
        default=0.5,
    )

    parser.add_option(
        '-t',
        '--time-out',
        action='store',
        type=float,
        dest='timeout',
        help='Set connection time-out. Default: 15 [sec].',
        default=15.,
    )

    (options, args) = parser.parse_args(argv)

    if options.cite:
        print('Reference for this software:')
        print(__reference__)
        print()
        print('Bibtex format:')
        print(__bibtex__)
        sys.exit(0)

    if len(args) > 0:
        try:
            options.record = str(int(args[0]))
        except ValueError:
            options.doi = args[0]
    elif options.doi is None and options.record is None:
        parser.print_help()
        sys.exit(0)

    if options.doi is not None:
        url = options.doi
        if not url.startswith('http'):
            url = 'https://doi.org/' + url
        try:
            r = requests.get(url, timeout=options.timeout)
        except requests.exceptions.ConnectTimeout:
            eprint('Connection timeout.')
            sys.exit(1)
        except Exception:
            eprint('Connection error.')
            sys.exit(1)
        if not r.ok:
            eprint('DOI could not be resolved. Try again, or use record ID.')
            sys.exit(1)
        recordID = r.url.split('/')[-1]
    else:
        recordID = options.record
    recordID = recordID.strip()

    url = 'https://zenodo.org/api/records/'
    try:
        r = requests.get(url + recordID, timeout=options.timeout)
    except requests.exceptions.ConnectTimeout:
        eprint('Connection timeout during metadata reading.')
        sys.exit(1)
    except Exception:
        eprint('Connection error during metadata reading.')
        sys.exit(1)

    if r.ok:
        js = json.loads(r.text)
        files = js['files']
        total_size = sum(f['size'] for f in files)

        if options.md5 is not None:
            with open('md5sums.txt', 'wt') as md5file:
                for f in files:
                    fname = f['key']
                    checksum = f['checksum'].split(':')[-1]
                    md5file.write(f'{checksum}  {fname}\n')

        if options.wget is not None:
            if options.wget == '-':
                for f in files:
                    link = f['links']['self']
                    print(link)
            else:
                with open(options.wget, 'wt') as wgetfile:
                    for f in files:
                        fname = f['key']
                        link = 'https://zenodo.org/record/{}/files/{}'.format(
                            recordID, fname
                        )
                        wgetfile.write(link + '\n')
        else:
            eprint('Title: {}'.format(js['metadata']['title']))
            eprint('Keywords: ' +
                   (', '.join(js['metadata'].get('keywords', []))))
            eprint('Publication date: ' + js['metadata']['publication_date'])
            eprint('DOI: ' + js['metadata']['doi'])
            eprint('Total size: {:.1f} MB'.format(total_size / 2 ** 20))

            for f in files:
                if abort_signal:
                    eprint('Download aborted with CTRL+C.')
                    eprint('Already successfully downloaded files are kept.')
                    break
                link = f['links']['self']
                size = f['size'] / 2 ** 20
                eprint()
                eprint(f'Link: {link}   size: {size:.1f} MB')
                fname = f['key']
                checksum = f['checksum']

                remote_hash, local_hash = check_hash(fname, checksum)

                if remote_hash == local_hash and options.cont:
                    eprint(f'{fname} is already downloaded correctly.')
                    continue

                for _ in range(options.retry + 1):
                    try:
                        filename = wget.download(link)
                    except Exception:
                        eprint('  Download error.')
                        time.sleep(options.pause)
                    else:
                        break
                else:
                    eprint('  Too many errors.')
                    if not options.error:
                        eprint('  Download is aborted.')
                        sys.exit(0)
                    eprint('  Download continues with the next file.')
                    continue

                eprint()
                h1, h2 = check_hash(filename, checksum)
                if h1 == h2:
                    eprint(f'Checksum is correct. ({h1})')
                else:
                    eprint(f'Checksum is INCORRECT!({h1} got:{h2})')
                    if not options.keep:
                        eprint('  File is deleted.')
                        os.remove(filename)
                    else:
                        eprint('  File is NOT deleted!')
                    if not options.error:
                        sys.exit(1)
            else:
                eprint('All files have been downloaded.')
    else:
        eprint('Record could not get accessed.')
        sys.exit(1)


if __name__ == '__main__':
    zenodo_get()
