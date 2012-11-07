"""
Various utilities for Varda.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


import hashlib

from flask import current_app
from vcf.utils import trim_common_suffix


from . import genome


class ReferenceError(Exception):
    """
    Exception thrown mismatch with reference.
    """
    pass


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
    Try to get normalized chromosome name by reference lookup.
    """
    chromosome_aliases = [['M', 'MT', 'NC_012920.1', 'chrM', 'chrMT']]

    if not genome:
        for aliases in chromosome_aliases:
            if chromosome in aliases:
                return aliases[0]
        if chromosome.startswith('chr'):
            return chromosome[3:]
        return chromosome

    if chromosome in genome:
        return chromosome

    if chromosome.startswith('chr'):
        if chromosome[3:] in genome:
            return chromosome[3:]
    else:
        if 'chr' + chromosome in genome:
            return 'chr' + chromosome

    for aliases in chromosome_aliases:
        if chromosome in aliases:
            for alias in aliases:
                if alias in genome:
                    return alias

    raise ReferenceError('Chromosome "%s" not in reference genome' % chromosome)


def normalize_variant(chromosome, position, reference, observed):
    """
    Use reference to create a normalized representation of the variant.
    """
    reference, observed = trim_common_suffix(reference.upper(), observed.upper())
    chromosome = normalize_chromosome(chromosome)

    if not genome:
        return chromosome, position, reference, observed

    if position > len(genome[chromosome]):
        raise ReferenceError('Position %d does not exist on chromosome "%s" in reference genome' % (position, chromosome))

    if genome[chromosome][position - 1:position + len(reference) - 1].upper() != reference:
        raise ReferenceError('Sequence "%s" does not match reference genome on "%s" at position %d' % (reference, chromosome, position))

    # Todo: force the variant as much as possible to the left.

    # Cases:
    # - deletion: roll deleted pattern
    # - duplication: roll duplicated pattern
    # - insertion: roll inserted pattern
    # - substitution: don't roll
    # - other indel: don't roll

    return chromosome, position, reference, observed


def move_left(sequence, begin, end):
    """
    Move ``begin-end`` (one-based, inclusive) in ``sequence`` as far as
    possible to the left while staying in cyclic permutations.
    """
    move = 0
    while (begin - move > 1 and
           sequence[begin - move - 2] == sequence[end - move - 1]):
        move += 1
    return move
