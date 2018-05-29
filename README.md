Zenodo_get: Downloader for Zenodo records
=========================================
Travis CI: [![Build Status](https://travis-ci.org/dvolgyes/zenodo_get.svg?branch=master)](https://travis-ci.org/dvolgyes/zenodo_get)
Semaphore: [![Build Status](https://semaphoreci.com/api/v1/dvolgyes/zenodo_get/branches/master/badge.svg)](https://semaphoreci.com/dvolgyes/zenodo_get)
CircleCI: [![Build status](https://circleci.com/gh/dvolgyes/zenodo_get.svg?style=svg)](https://circleci.com/gh/dvolgyes/zenodo_get)
AppVeyor: [![Build status](https://ci.appveyor.com/api/projects/status/f6hw96rhdl104ch9?svg=true)](https://ci.appveyor.com/project/dvolgyes/zenodo-get)

Coveralls: [![Coverage Status](https://img.shields.io/coveralls/github/dvolgyes/zenodo_get/master.svg)](https://coveralls.io/github/dvolgyes/zenodo_get?branch=master)
Codecov: [![codecov](https://codecov.io/gh/dvolgyes/zenodo_get/branch/master/graph/badge.svg)](https://codecov.io/gh/dvolgyes/zenodo_get)

This is a Python3 tool which can mass-download files from Zenodo records.

Minimum Python version is 3.6, but if there is a strong demand, I could port it to older versions too.


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
The tool itself is simple, the help message is reasonable:

```
zenodo_get.py -h
```

but if you need more, open a github ticket and explain what is missing.
