import sys
from setuptools import setup

if sys.version_info < (2, 7):
    raise Exception('Varda requires Python 2.7 or higher.')

# Todo: How does this play with pip freeze requirement files?
requires = []

import varda as distmeta

setup(
    name='varda',
    version=distmeta.__version__,
    description='A database for genomic variation frequencies',
    long_description=distmeta.__doc__,
    author=distmeta.__author__,
    author_email=distmeta.__contact__,
    url=distmeta.__homepage__,
    license='MIT License',
    platforms=['any'],
    packages=['varda'],
    requires=requires,
    entry_points = {
        'console_scripts': ['varda = varda.commands:main']
        },
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering',
        ],
    keywords='bioinformatics'
)
