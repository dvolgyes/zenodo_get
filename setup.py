#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools
import src.zenodo_get as zget

setuptools.setup(
    name=zget.__title__,
    version=zget.__version__,
    author=zget.__author__,
    author_email=zget.__email__,
    description=zget.__summary__,
    description_content_type='text/plain',
    long_description=zget.__description__,
    long_description_content_type='text/markdown',
    url=zget.__uri__,
    license=zget.__license__,
    packages=setuptools.find_packages(),
    scripts=['src/zenodo_get.py'],
    python_requires='>=2.7',
    setup_requires=['future-fstrings'],
    install_requires=['requests', 'wget', 'future-fstrings'],
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
