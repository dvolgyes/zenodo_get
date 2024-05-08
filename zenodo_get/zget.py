#!/usr/bin/env python3
import hashlib
import os
import requests
import signal
import sys
import time
import wget
import zenodo_get as zget
from contextlib import contextmanager
from fnmatch import fnmatch
from optparse import OptionParser
from pathlib import Path
from urllib.parse import unquote


# see https://stackoverflow.com/questions/431684/how-do-i-change-the-working-directory-in-python/24176022#24176022
@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def ctrl_c(func):
    signal.signal(signal.SIGINT, func)
    return func


abort_signal = False
abort_counter = 0
exceptions = False


@ctrl_c
def handle_ctrl_c(*args, **kwargs):
    global abort_signal
    global abort_counter
    global exceptions

    abort_signal = True
    abort_counter += 1

    if abort_counter >= 2:
        eprint()
        eprint("Immediate abort. There might be unfinished files.")
        if exceptions:
            raise Exception("Immediate abort")
        else:
            sys.exit(1)


def check_hash(filename, checksum):
    algorithm = "md5"
    value = checksum.strip()
    if not os.path.exists(filename):
        return value, "invalid"
    h = hashlib.new(algorithm)
    with open(filename, "rb") as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            h.update(data)
    digest = h.hexdigest()
    return value, digest


def zenodo_get(argv=None):
    global exceptions

    if argv is None:
        argv = sys.argv[1:]
        exceptions = False
    else:
        exceptions = True

    parser = OptionParser(
        usage="%prog [options] RECORD_OR_DOI", version=f"%prog {zget.__version__}"
    )

    parser.add_option(
        "-c",
        "--cite",
        dest="cite",
        action="store_true",
        default=False,
        help="print citation information",
    )

    parser.add_option(
        "-r",
        "--record",
        action="store",
        type="string",
        dest="record",
        help="Zenodo record ID",
        default=None,
    )

    parser.add_option(
        "-d",
        "--doi",
        action="store",
        type="string",
        dest="doi",
        help="Zenodo DOI",
        default=None,
    )

    parser.add_option(
        "-m",
        "--md5",
        action="store_true",
        # ~type=bool,
        dest="md5",
        help="Create md5sums.txt for verification.",
        default=False,
    )

    parser.add_option(
        "-w",
        "--wget",
        action="store",
        type="string",
        dest="wget",
        help="Create URL list for download managers. "
        "(Files will not be downloaded.)",
        default=None,
    )

    parser.add_option(
        "-e",
        "--continue-on-error",
        action="store_true",
        dest="error",
        help="Continue with next file if error happens.",
        default=False,
    )

    parser.add_option(
        "-k",
        "--keep",
        action="store_true",
        dest="keep",
        help="Keep files with invalid checksum." " (Default: delete them.)",
        default=False,
    )

    parser.add_option(
        "-n",
        "--do-not-continue",
        action="store_false",
        dest="cont",
        help="Do not continue previous download attempt. (Default: continue.)",
        default=True,
    )

    parser.add_option(
        "-R",
        "--retry",
        action="store",
        type=int,
        dest="retry",
        help="Retry on error N more times.",
        default=0,
    )

    parser.add_option(
        "-p",
        "--pause",
        action="store",
        type=float,
        dest="pause",
        help="Wait N second before retry attempt, e.g. 0.5",
        default=0.5,
    )

    parser.add_option(
        "-t",
        "--time-out",
        action="store",
        type=float,
        dest="timeout",
        help="Set connection time-out. Default: 15 [sec].",
        default=15.0,
    )

    parser.add_option(
        "-o",
        "--output-dir",
        action="store",
        type=str,
        dest="outdir",
        default=".",
        help="Output directory, created if necessary. Default: current directory.",
    )

    parser.add_option(
        "-s",
        "--sandbox",
        action="store_true",
        dest="sandbox",
        help="Use Zenodo Sandbox URL.",
        default=False,
    )

    parser.add_option(
        "-a",
        "--access-token",
        action="store",
        type=str,
        dest="access_token",
        default=None,
        help="Optional access token for the requests query.",
    )

    parser.add_option(
        "-g",
        "--glob",
        action="store",
        type=str,
        dest="glob",
        default="*",
        help="Optional glob expression for files.",
    )

    (options, args) = parser.parse_args(argv)

    if options.cite:
        print("Reference for this software:")
        print(zget.__reference__)
        print()
        print("Bibtex format:")
        print(zget.__bibtex__)
        if exceptions:
            return
        else:
            sys.exit(0)

    # create directory, if necessary, then change to it
    options.outdir = Path(options.outdir)
    options.outdir.mkdir(parents=True, exist_ok=True)
    with cd(options.outdir):
        if len(args) > 0:
            try:
                options.record = str(int(args[0]))
            except ValueError:
                options.doi = args[0]
        elif options.doi is None and options.record is None:
            parser.print_help()
            if exceptions:
                return
            else:
                sys.exit(0)

        if options.doi is not None:
            url = options.doi
            if not url.startswith("http"):
                url = "https://doi.org/" + url
            try:
                r = requests.get(url, timeout=options.timeout)
            except requests.exceptions.ConnectTimeout:
                eprint("Connection timeout.")
                if exceptions:
                    raise
                else:
                    sys.exit(1)
            except Exception:
                eprint("Connection error.")
                if exceptions:
                    raise
                else:
                    sys.exit(1)
            if not r.ok:
                eprint("DOI could not be resolved. Try again, or use record ID.")
                if exceptions:
                    raise ValueError("DOI", options.doi)
                else:
                    sys.exit(1)

            recordID = r.url.split("/")[-1]
        else:
            recordID = options.record
        recordID = recordID.strip()

        if not options.sandbox:
            url = "https://zenodo.org/api/records/"
        else:
            url = "https://sandbox.zenodo.org/api/records/"

        params = {}
        if options.access_token:
            params["access_token"] = options.access_token

        try:
            r = requests.get(url + recordID, params=params, timeout=options.timeout)
        except requests.exceptions.ConnectTimeout:
            eprint("Connection timeout during metadata reading.")
            if exceptions:
                raise
            else:
                sys.exit(1)
        except Exception:
            eprint("Connection error during metadata reading.")
            if exceptions:
                raise
            else:
                sys.exit(1)

        if r.ok:
            js = r.json()
            files = [
                f
                for f in js["files"]
                if fnmatch(f.get("filename") or f["key"], options.glob)
            ]
            if not files:
                eprint("Files {} not found in metadata".format(options.glob))

            total_size = sum((f.get("filesize") or f["size"]) for f in files)

            if options.md5 is not None:
                with open("md5sums.txt", "wt") as md5file:
                    for f in files:
                        fname = f.get("filename") or f["key"]
                        checksum = f["checksum"].split(":")[-1]
                        md5file.write(f"{checksum}  {fname}\n")

            if options.wget is not None:
                if options.wget == "-":
                    for f in files:
                        fname = f.get("filename") or f["key"]
                        link = "https://zenodo.org/records/{}/files/{}".format(
                            recordID, fname
                        )
                        print(link)
                else:
                    with open(options.wget, "wt") as wgetfile:
                        for f in files:
                            fname = f.get("filename") or f["key"]
                            link = "https://zenodo.org/records/{}/files/{}".format(
                                recordID, fname
                            )
                            wgetfile.write(link + "\n")
            else:
                eprint("Title: {}".format(js["metadata"]["title"]))
                eprint("Keywords: " + (", ".join(js["metadata"].get("keywords", []))))
                eprint("Publication date: " + js["metadata"]["publication_date"])
                eprint("DOI: " + js["metadata"]["doi"])
                eprint("Total size: {:.1f} MB".format(total_size / 2**20))

                for f in files:
                    if abort_signal:
                        eprint("Download aborted with CTRL+C.")
                        eprint("Already successfully downloaded files are kept.")
                        break

                    fname = f.get("filename") or f["key"]
                    link = "https://zenodo.org/records/{}/files/{}".format(
                        recordID, fname
                    )

                    size = (f.get("filesize") or f["size"]) / 2**20
                    eprint()
                    eprint(f"Link: {link}   size: {size:.1f} MB")
                    fname = f.get("filename") or f["key"]
                    checksum = f["checksum"].split(":")[-1]

                    remote_hash, local_hash = check_hash(fname, checksum)

                    if remote_hash == local_hash and options.cont:
                        eprint(f"{fname} is already downloaded correctly.")
                        continue

                    for _ in range(options.retry + 1):
                        try:
                            link = url = unquote(link)
                            filename = wget.download(
                                f"{link}?access_token={options.access_token}"
                            )
                        except Exception:
                            eprint(f"  Download error. Original link: {link}")
                            time.sleep(options.pause)
                        else:
                            break
                    else:
                        eprint("  Too many errors.")
                        if not options.error:
                            eprint("  Download is aborted.")
                            if exceptions:
                                raise Exception("too  many errors")
                            else:
                                sys.exit(1)
                        eprint("  Download continues with the next file.")
                        continue

                    eprint()
                    h1, h2 = check_hash(filename, checksum)
                    if h1 == h2:
                        eprint(f"Checksum is correct. ({h1})")
                    else:
                        eprint(f"Checksum is INCORRECT!({h1} got:{h2})")
                        if not options.keep:
                            eprint("  File is deleted.")
                            os.remove(filename)
                        else:
                            eprint("  File is NOT deleted!")
                        if not options.error:
                            sys.exit(1)
                else:
                    eprint("All files have been downloaded.")
        else:
            eprint("Record could not get accessed.")
            if exceptions:
                raise Exception("Record could not get accessed.")
            else:
                sys.exit(1)
