"""
Various utilities for Varda.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import hashlib


def calculate_digest(data):
    """
    Given a file-like object opened for reading, calculate a digest string
    using SHA1.
    """
    def read_chunks(data, chunksize=0xf00000):
        # Default chunksize is 16 megabytes.
        while True:
            chunk = data.read(chunksize)
            if not chunk:
                break
            yield chunk

    sha1 = hashlib.sha1()
    for chunk in read_chunks(data):
        sha1.update(chunk)
    return sha1.hexdigest()


def normalize_chromosome(chromosome):
    """
    Remove 'chr' prefix from chromosome names and store NC_012920 as
    chromosome 'M'.
    """
    if chromosome.startswith('NC_012920'):
        return 'M'
    if chromosome.startswith('chr'):
        return chromosome[3:]
    return chromosome
