#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

short_description = 'Zenodo_get - Downloader for Zenodo records'
long_description = """
Zenodo_get - a downloader for Zenodo records
============================================

Zenodo.org is a scientific data repository.
However, it lacks an easy to use solution to download all files from a
given deposit. This project aims to solve this situation.
"""

setuptools.setup(
    name='zenodo_get',
    version='1.0.1',
    author='David Volgyes',
    author_email='david.volgyes@ieee.org',
    description=short_description,
    description_content_type='text/plain',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://gitlab.com/dvolgyes/zenodo_get',
    license='AGPL',
    packages=setuptools.find_packages(),
    scripts=['src/zenodo_get.py'],
    python_requires='>=2.7',
    setup_requires=[],
    install_requires=['requests', 'wget'],
    keywords='zenodo download',
    classifiers=(
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU Affero General Public License v3',
    ),

)
