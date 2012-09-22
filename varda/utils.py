"""
Various utilities for Varda.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import hashlib


def digest(data):
    """
    Given a file-like object opened for reading, calculate a digest as SHA1
    checksum and number of records.

    Calculating the number of records is done in a naive way by counting the
    number of lines in the file, and as such includes empty and header lines.
    """
    def read_chunks(data, chunksize=0xf00000):
        # Default chunksize is 16 megabytes.
        while True:
            chunk = data.read(chunksize)
            if not chunk:
                break
            yield chunk

    sha1 = hashlib.sha1()
    records = 0
    for chunk in read_chunks(data):
        sha1.update(chunk)
        records += chunk.count('\n')
    return sha1.hexdigest(), records


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
