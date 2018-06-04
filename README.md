zenodo_get: a downloader for Zenodo records
===========================================
Travis CI: [![Build Status](https://travis-ci.org/dvolgyes/zenodo_get.svg?branch=master)](https://travis-ci.org/dvolgyes/zenodo_get)
Semaphore: [![Build Status](https://semaphoreci.com/api/v1/dvolgyes/zenodo_get/branches/master/badge.svg)](https://semaphoreci.com/dvolgyes/zenodo_get)
CircleCI: [![Build status](https://circleci.com/gh/dvolgyes/zenodo_get.svg?style=svg)](https://circleci.com/gh/dvolgyes/zenodo_get)
AppVeyor: [![Build status](https://ci.appveyor.com/api/projects/status/f6hw96rhdl104ch9?svg=true)](https://ci.appveyor.com/project/dvolgyes/zenodo-get)

Coveralls: [![Coverage Status](https://coveralls.io/repos/github/dvolgyes/zenodo_get/badge.svg?branch=master)](https://coveralls.io/github/dvolgyes/zenodo_get?branch=master)
Codecov: [![codecov](https://codecov.io/gh/dvolgyes/zenodo_get/branch/master/graph/badge.svg)](https://codecov.io/gh/dvolgyes/zenodo_get)

This is a Python3 tool which can mass-download files from Zenodo records.

[![pyversion](https://img.shields.io/pypi/pyversions/zenodo_get.svg)](https://test.pypi.org/project/zenodo-get/) Minimum Python version is 2.7 or 3.5, but if there is a strong demand, I could port it to older versions too.


Install
-------

```
pip3 install git+https://github.com/dvolgyes/zenodo_get
```

Afterwards, you can query the command line options:
```
zenodo_get.py -h
```

but the default settings should work for most use cases:
```
zenodo_get.py RECORD_ID_OR_DOI
```


Documentation
-------------
The tool itself is simple, and the help message is reasonable:

```
zenodo_get.py -h
```

but if you need more, open a github ticket and explain what is missing.

Basic usage:
```
zenodo_get.py RECORD_ID_OR_DOI
```

Special parameters:
- ``-m`` : generate md5sums.txt for verification. Beware, if `md5sums.txt` is
  present in the dataset, it will overwrite this generated file. Verification example:
  `md5sum -c md5sums.txt`
- ``-w FILE`` : instead of downloading the record files, it will
   generate a FILE which contains direct links to the Zenodo site. These links
   could be downloaded with any download manager, e.g. with wget:
   `wget -i urls.txt`
- ``-e`` : continue on error. It will skip the files with errors, but it will
    try to download the rest of the files.
- ``-k`` : keep files: it will keep files with invalid md5 checksum. The main purpose
   is debugging.
- ``-R N``: retry on error N times.
- ``-p N``: Waiting time in sec before retry attempt. Default: 0.5 sec.
- ``-n`` : do not continue. The default behaviour is to download only the files
   which are not yet download or where the checksum does not match with the file.
   This flag disables this feature, and it will force download existing files,
   and assigining a new name to the files (e.g. file(1).ext )


Remark for batch processing: the program always exits with non-zero exit code, if any error has happened,
for instance, checksum mismatch, download error, time-out, etc. Only perfectly correct
downloads end with 0 exit code.
