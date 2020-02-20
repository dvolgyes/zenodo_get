#!/usr/bin/env python

import setuptools
import zenodo_get as zget

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
    entry_points={'console_scripts': ['zenodo_get = zenodo_get:zenodo_get']},
    python_requires='>=3.6',
    setup_requires=[],
    install_requires=['requests', 'wget'],
    keywords='zenodo download',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU Affero General Public License v3',
    ],
)
