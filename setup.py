#!/usr/bin/env python
# -*- coding: utf-8 -*-
from distutils.core import setup
from distutils.util import get_platform


short_description = 'Zenodo_get - Downloader for Zenodo records'

with open('requirements.txt', 'rt') as f:
    reqs = list(map(str.strip, f.readlines()))

setup(
    name='zenodo_get',
    version='1.0.0',
    description=short_description,
    long_description=short_description,
    author='David Volgyes',
    author_email='david.volgyes@ieee.org',
    url='https://github.com/dvolgyes/zenodo_get',
    packages=['zenodo_get'],
    package_dir={'zenodo_get': 'src'},
    scripts=['src/zenodo_get.py'],
    data_files=[],
    keywords=['zenodo', 'download'],
    classifiers=[],
    license='AGPL3',
    platforms=[get_platform()],
    require=reqs,
    download_url='https://github.com/dvolgyes/zenodo_get/archive/latest.tar.gz'
)
