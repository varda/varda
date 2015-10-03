"""
Celery tasks.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


# Todo: Really only have Celery tasks in this file, anything that can in
#     principle be used without Celery should be defined elsewhere.


from __future__ import division

from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import itertools
import os
import time
import uuid

from celery import current_task, current_app, Task, states
from celery.utils.log import get_task_logger
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from vcf.parser import _Info as VcfInfo, field_counts as vcf_field_counts
import vcf

from . import db, celery
from .models import (Annotation, Coverage, DataSource, DataUnavailable,
                     Observation, Sample, Region, Variation)
from .region_binning import all_bins
from .utils import (calculate_frequency, digest, NoGenotypesInRecord,
                    normalize_variant, normalize_chromosome, normalize_region,
                    read_genotype, ReferenceMismatch)


# Number of records to buffer before committing to the database.
DB_BUFFER_SIZE = 5000


logger = get_task_logger(__name__)


class ReadError(Exception):
    """
    Exception thrown on failed data reading.
    """
    pass


class TaskError(Exception):
    """
    Exception thrown on failed task execution.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(TaskError, self).__init__(code, message)


class VardaTask(Task):
    """
    Celery base task class that should be used for all tasks.
    """
    abstract = True

    # https://gist.github.com/winhamwr/2719812
    def on_success(self, retval, task_id, args, kwargs):
        """
        Store results in the backend even if we're always eager. This helps
        for testing.
        """
        if current_app.conf.get('CELERY_ALWAYS_EAGER', False):
            # Store the result because Celery wouldn't otherwise.
            self.backend.store_result(task_id, retval, status=states.SUCCESS)


class CleanTask(VardaTask):
    """
    Ordinary Celery task, but with a way of registering cleanup routines that
    are executed after the task failed (on the worker node).
    """
    abstract = True

    # We maintain a list of cleanups per task id since the worker node only
    # instantiates the task class once (not for every run). Just storing one
    # list of cleanups in this instance would mean they are shared between
    # different task runs.
    _cleanups = defaultdict(list)

    def register_cleanup(self, task_id, cleanup):
        self._cleanups[task_id].append(cleanup)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        for cleanup in reversed(self._cleanups[task_id]):
            cleanup()
        del self._cleanups[task_id]


def annotate_data_source(original, annotated_variants,
                         original_filetype='vcf', **kwargs):
    """
    Read variants or regions from a file and write them to another file with
    frequency annotation.

    This is a shortcut function for :func:`annotate_variants` or
    :func:`annotate_regions`, depending on the value of `original_filetype`.
    See their respective docstrings for more information.
    """
    if original_filetype == 'vcf':
        annotate_variants(original, annotated_variants,
                          original_filetype=original_filetype, **kwargs)
    else:
        annotate_regions(original, annotated_variants,
                         original_filetype=original_filetype, **kwargs)


def annotate_variants(original_variants, annotated_variants,
                      original_filetype='vcf', annotated_filetype='vcf',
                      queries=None, original_records=1):
    """
    Read variants from a file and write them to another file with frequency
    annotation.

    :arg original_variants: Open handle to a file with variants.
    :type original_variants: file-like object
    :arg annotated_variants: Open handle to write annotated variants to.
    :type annotated_vairants: file-like object
    :kwarg original_filetype: Filetype for variants (currently only ``vcf``
        allowed).
    :type original_filetype: str
    :kwarg annotated_filetype: Filetype for annotated variants (currently only
        ``vcf`` allowed).
    :type annotated_filetype: str
    :arg queries: List of sample queries to compute frequencies over.
    :type queries: list of Query
    :arg original_records: Number of records in original variants file.
    :type original_records: int

    Frequency information is annotated using fields in the INFO column. For
    each query, we use the following fields, where the ``<Q>`` prefix is the
    query name:

    - ``<Q>_VN``: For each alternate allele, the number of individuals used
      for calculating ``<Q>_VF``, i.e., the number of individuals that have
      this region covered.
    - ``<Q>_VF``: For each alternate allele, the observed frequency, i.e., the
      ratio of individuals in which the allele was observed.
    - ``<Q>_VF_HET``: For each alternate allele, the observed heterozygous
      frequency, i.e., the ratio of individuals in which the allele was
      observed heterozygous.
    - ``<Q>_VF_HOM``: For each alternate allele, the observed homozygous
      frequency, i.e., the ratio of individuals in which the allele was
      observed homozygous.

    Note that the ``<Q>_VF_HET`` and ``<Q>_VF_HOM`` values for a particular
    alternate allele might not add up to the ``<Q>_VF`` value, since there can
    be observations where the exact genotype is unknown.

    If the query specifies exactly one sample and that sample does not have
    coverage information, ``<Q>_VN`` is simply the number of individuals
    contained in the sample.
    """
    queries = queries or []

    if original_filetype != 'vcf':
        raise ReadError('Original data must be in VCF format')

    if annotated_filetype != 'vcf':
        raise ReadError('Annotated data must be in VCF format')

    reader = vcf.Reader(original_variants)

    # Header lines in VCF output for each query.
    for query in queries:
        description = ('Number of individuals in %s having this region covered'
                       % query.name)
        if not query.require_coverage_profile:
            description += ' (or without coverage profile)'
        description += ' (out of %i considered)' % sum(sample.pool_size for
                                                       sample in query.samples)
        reader.infos[query.name + '_VN'] = VcfInfo(
            query.name + '_VN', vcf_field_counts['A'], 'Integer', description)
        reader.infos[query.name + '_VF'] = VcfInfo(
            query.name + '_VF', vcf_field_counts['A'], 'Float',
            'Ratio of individuals in %s in which the allele was observed.' %
            query.name)
        reader.infos[query.name + '_VF_HET'] = VcfInfo(
            query.name + '_VF_HET', vcf_field_counts['A'], 'Float',
            'Ratio of individuals in %s in which the allele was observed as '
            'heterozygous.' % query.name)
        reader.infos[query.name + '_VF_HOM'] = VcfInfo(
            query.name + '_VF_HOM', vcf_field_counts['A'], 'Float',
            'Ratio of individuals in %s in which the allele was observed as '
            'homozygous.' % query.name)

    writer = vcf.Writer(annotated_variants, reader, lineterminator='\n')

    # Number of lines read (i.e. comparable to what is reported by
    # ``varda.utils.digest``).
    current_record = len(reader._header_lines) + 1

    old_percentage = -1
    for record in reader:
        current_record += 1
        percentage = min(int(current_record / original_records * 100), 99)
        if percentage > old_percentage:
            # Todo: Task state updating should be defined in the task itself,
            #     perhaps we can give values using a callback.
            try:
                current_task.update_state(state='PROGRESS',
                                          meta={'percentage': percentage})
            except AttributeError:
                # Hack for the unit tests were whe call this not from within
                # a task.
                pass
            old_percentage = percentage

        results = [[] for _ in queries]
        for index, allele in enumerate(record.ALT):
            try:
                chromosome, position, reference, observed = normalize_variant(
                    record.CHROM, record.POS, record.REF, str(allele))
            except ReferenceMismatch as e:
                raise ReadError(str(e))

            for i, query in enumerate(queries):
                results[i].append(calculate_frequency(chromosome, position,
                                                      reference, observed,
                                                      samples=query.samples))

        for query, result in zip(queries, results):
            record.add_info(query.name + '_VN', [vn for vn, _ in result])
            record.add_info(query.name + '_VF', [sum(vf.values()) for _, vf in result])
            record.add_info(query.name + '_VF_HET', [vf['heterozygous'] for _, vf in result])
            record.add_info(query.name + '_VF_HOM', [vf['homozygous'] for _, vf in result])

        writer.write_record(record)


def annotate_regions(original_regions, annotated_variants,
                     original_filetype='bed', annotated_filetype='csv',
                     queries=None, original_records=1):
    """
    Read regions from a file and write variant frequencies to another file.

    :arg original_regions: Open handle to a file with regions.
    :type original_regions: file-like object
    :arg annotated_variants: Open handle to write annotated variants to.
    :type annotated_vairants: file-like object
    :kwarg original_filetype: Filetype for variants (currently only ``bed``
        allowed).
    :type original_filetype: str
    :kwarg annotated_filetype: Filetype for annotated variants (currently only
        ``csv`` allowed).
    :type annotated_filetype: str
    :arg queries: List of sample queries to compute frequencies over.
    :type queries: list of Query
    :arg original_records: Number of records in original regions file.
    :type original_records: int

    The output file contains the following columns for information on each
    variant:

    - ``CHROMOSOME``: Chromosome name in the reference genome.
    - ``POSITION``: One-based position of ``REFERENCE`` and ``OBSERVED`` on
      ``CHROMOSOME``.
    - ``REFERENCE``: Reference allele.
    - ``OBSERVED``: Observed (alternate) allele.

    Frequency information is annotated using several additional columns in the
    output file. For each query, we use the following columns, where the
    ``<Q>`` prefix is the query name:

    - ``<Q>_VN``: For each alternate allele, the number of individuals used
      for calculating ``<Q>_VF``, i.e., the number of individuals that have
      this region covered.
    - ``<Q>_VF``: For each alternate allele, the observed frequency, i.e., the
      ratio of individuals in which the allele was observed.
    - ``<Q>_VF_HET``: For each alternate allele, the observed heterozygous
      frequency, i.e., the ratio of individuals in which the allele was
      observed heterozygous.
    - ``<Q>_VF_HOM``: For each alternate allele, the observed homozygous
      frequency, i.e., the ratio of individuals in which the allele was
      observed homozygous.

    Note that the ``<Q>_VF_HET`` and ``<Q>_VF_HOM`` values for a particular
    alternate allele might not add up to the ``<Q>_VF`` value, since there can
    be observations where the exact genotype is unknown.

    If the query specifies exactly one sample and that sample does not have
    coverage information, ``<Q>_VN`` is simply the number of individuals
    contained in the sample.
    """
    queries = queries or []

    if original_filetype != 'bed':
        raise ReadError('Original data must be in BED format')

    if annotated_filetype != 'csv':
        raise ReadError('Annotated data must be in CSV format')

    # Set of samples IDs that are considered by all queries together.
    all_sample_ids = {sample.id
                      for query in queries
                      for sample in query.samples}

    header_fields = ['CHROMOSOME', 'POSITION', 'REFERENCE', 'OBSERVED']

    # Header lines in CSV output for each query.
    for query in queries:
        header_fields.extend([query.name + '_VN', query.name + '_VF',
                              query.name + '_VF_HET', query.name + '_VF_HOM'])
        description = ('Number of individuals in %s having this region covered'
                       % query.name)
        if not query.require_coverage_profile:
            description += ' (or without coverage profile)'
        description += ' (out of %i considered).' % sum(sample.pool_size for
                                                        sample in query.samples)
        # TODO: If it is a singleton query, removing the "... having this
        # region covered ..." part.
        annotated_variants.write(
            '##' + query.name + '_VN: %s.\n' % description)
        annotated_variants.write(
            '##' + query.name + '_VF: Ratio of individuals in %s in which the '
            'allele was observed.\n' % query.name)
        annotated_variants.write(
            '##' + query.name + '_VF_HET: Ratio of individuals in %s in which the '
            'allele was observed as heterozygous.\n' % query.name)
        annotated_variants.write(
            '##' + query.name + '_VF_HOM: Ratio of individuals in %s in which the '
            'allele was observed as homozygous.\n' % query.name)

    annotated_variants.write('#' + '\t'.join(header_fields) + '\n')

    old_percentage = -1
    for current_record, chromosome, begin, end in read_regions(original_regions):
        percentage = min(int(current_record / original_records * 100), 99)
        if percentage > old_percentage:
            # Todo: Task state updating should be defined in the task itself,
            #     perhaps we can give values using a callback.
            try:
                current_task.update_state(state='PROGRESS',
                                          meta={'percentage': percentage})
            except AttributeError:
                # Hack for the unit tests were whe call this not from within
                # a task.
                pass
            old_percentage = percentage

        results = [[] for _ in queries]

        # Set of observations considered by all queries together.
        bins = all_bins(begin, end)
        observations = Observation.query.filter(
            Observation.chromosome == chromosome,
            Observation.position >= begin,
            Observation.position <= end,
            Observation.bin.in_(bins)
        ).join(Variation).join(Sample).filter(
            Sample.id.in_(all_sample_ids)
        ).distinct(
            Observation.chromosome,
            Observation.position,
            Observation.reference,
            Observation.observed
        ).order_by(
            Observation.chromosome,
            Observation.position,
            Observation.reference,
            Observation.observed,
            Observation.id
        )

        for observation in observations:
            fields = [observation.chromosome, observation.position,
                      observation.reference, observation.observed]

            for query in enumerate(queries):
                vn, vf = calculate_frequency(observation.chromosome,
                                             observation.position,
                                             observation.reference,
                                             observation.observed,
                                             samples=query.samples)
                fields.extend([vn, sum(vf.values()), vf['heterozygous'],
                               vf['homozygous']])

            # Todo: Stringify per value, not in one sweep.
            annotated_variants.write('\t'.join(str(f) for f in fields) + '\n')


def read_observations(observations, filetype='vcf', skip_filtered=True,
                      use_genotypes=True, prefer_genotype_likelihoods=False):
    """
    Read variant observations from a file and yield them one by one.

    :arg observations: Open handle to a file with variant observations.
    :type observations: file-like object
    :kwarg filetype: Filetype (currently only ``vcf`` allowed).
    :type filetype: str
    :kwarg skip_filtered: Whether or not to skip variants annotated as being
        filtered.
    :type skip_filtered: bool
    :kwarg use_genotypes: Whether or not to use genotypes (if available).
    :type use_genotypes: bool
    :kwarg prefer_genotype_likelihoods: Whether or not to prefer deriving
        genotypes from likelihoods (if available).
    :type prefer_genotype_likelihoods: bool

    :return: Generator yielding tuples (current_record, chromosome, position,
        reference, observed, zygosity, support).
    """
    if filetype != 'vcf':
        raise ReadError('Data must be in VCF format')

    reader = vcf.Reader(observations)

    # Todo: We could do an educated guess for optimal import parameters based
    #     on the contents of the VCF file. For example, with samtools VCF
    #     files we should usually not depend on GT but use PL [1]. We can
    #     check if a file was produced by samtools like this:
    #
    #       'samtoolsVersion' in reader.metadata
    #
    #     This could be activated by some --auto-settings parameter or
    #     something like it.
    #
    #     [1] http://www.biostars.org/p/12354/

    # Number of lines read (i.e. comparable to what is reported by
    # ``varda.utils.digest``).
    current_record = len(reader._header_lines) + 1

    for record in reader:
        current_record += 1

        if skip_filtered and record.FILTER:
            continue

        if 'SV' in record.INFO:
            # For now we ignore these, reference is likely to be larger than
            # the maximum of 200 by the database schema.
            # Example use of this type are large deletions in 1000 Genomes.
            continue

        # For each ALT, store sample count per zygosity (het, hom, or unkown).
        # For a diploid chromosome, the result will be something like:
        #
        #     # - first alt: 327 het, 7 unknown
        #     # - second alt: 73 het
        #     # - third alt: 154 hom, 561 het
        #     alt_support =
        #         [{'heterozygous': 327, None: 7},
        #          {'heterozygous': 73},
        #          {'homozygous': 154, 'heterozygous': 561}]
        #
        # The None value is used for the unknown genotype.
        alt_support = [Counter() for _ in record.ALT]

        # Todo: Use constants for zygosity, re-use them for a database enum.

        # In the case where we don't have genotypes or don't want to use them,
        # we look for a GTC (genotype counts) field containing, well, a count
        # for each genotype.
        # Our last resort is to just count the number of samples and store an
        # unknown zygosity. But only if there is exactly one ALT.

        if use_genotypes and record.samples:
            for call in record.samples:
                try:
                    genotype = read_genotype(call, prefer_genotype_likelihoods)
                except NoGenotypesInRecord:
                    # Exception will be raised for all calls in this record,
                    # so we can define the aggregate result and break.
                    if len(record.ALT) == 1:
                        alt_support = [{None: len(record.samples)}]
                    break

                if genotype:
                    counts = Counter(a for a in genotype)
                    # Todo: Option to ignore zygosity.
                    if len(counts) > 1:
                        zygosity = 'heterozygous'
                    else:
                        zygosity = 'homozygous'
                    for index, count in counts.items():
                        if index > 0:
                            alt_support[index - 1][zygosity] += 1

        elif 'GTC' in record.INFO:
            # All possible genotypes given alleles and call ploidy. Example
            # (diploid, two alt alleles):
            #
            #     genotypes = [(0, 0), (0, 1), (1, 1), (0, 2), (1, 2), (2, 2)]
            #
            # Todo: Make a function out of this, it is also used in the
            #     read_genotype function.
            # Todo: We could deduce ploidy from len(record.ALT) and
            #     len(record.INFO['GTC'] but for now we don't bother.
            ploidy = 2
            genotypes = sorted(itertools.combinations_with_replacement(
                                 range(len(record.ALT) + 1), ploidy),
                               key=lambda g: g[::-1])

            for genotype, sample_count in zip(genotypes, record.INFO['GTC']):
                if sample_count < 1:
                    continue
                counts = Counter(a for a in genotype)
                if len(counts) > 1:
                    zygosity = 'heterozygous'
                else:
                    zygosity = 'homozygous'
                for index, count in counts.items():
                    if index > 0:
                        alt_support[index - 1][zygosity] += sample_count

        elif len(record.ALT) == 1:
            if record.samples is None:
                alt_support = [{None: 1}]
            else:
                alt_support = [{None: len(record.samples)}]

        for index, allele in enumerate(record.ALT):
            try:
                chromosome, position, reference, observed = normalize_variant(
                    record.CHROM, record.POS, record.REF, str(allele))
            except ReferenceMismatch as e:
                logger.info('Reference mismatch: %s', str(e))
                if current_app.conf['REFERENCE_MISMATCH_ABORT']:
                    raise ReadError(str(e))
                continue

            # Todo: Ignore or abort?
            if len(reference) > 200 or len(observed) > 200:
                continue

            for zygosity, support in alt_support[index].items():
                yield (current_record, chromosome, position, reference,
                       observed, zygosity, support)


def read_regions(regions, filetype='bed'):
    if filetype != 'bed':
        raise ReadError('Data must be in BED format')

    for current_record, line in enumerate(regions):
        fields = line.split()
        if len(fields) < 1 or fields[0] == 'track':
            continue
        try:
            chromosome, begin, end = normalize_region(
                fields[0], int(fields[1]), int(fields[2]))
        except (IndexError, ValueError):
            raise ReadError('Invalid line in BED file: "%s"' % line)
        except ReferenceMismatch as e:
            logger.info('Reference mismatch: %s', str(e))
            if current_app.conf['REFERENCE_MISMATCH_ABORT']:
                raise ReadError(str(e))
            continue
        # Regions in a BED track are zero-based and open-ended, but our
        # regions are one-based and inclusive.
        yield current_record, chromosome, begin + 1, end


@celery.task(base=CleanTask)
def import_variation(variation_id):
    """
    Import variation as observations.
    """
    logger.info('Started task: import_variation(%d)', variation_id)

    current_task.update_state(state='PROGRESS', meta={'percentage': 0})

    variation = Variation.query.get(variation_id)
    if variation is None:
        raise TaskError('variation_not_found', 'Variation not found')

    if variation.task_done:
        raise TaskError('variation_imported', 'Variation already imported')

    if variation.task_uuid and variation.task_uuid != current_task.request.id:
        raise TaskError('variation_importing', 'Variation is being imported '
                        'by another task instance')

    data_source = variation.data_source

    # Calculate data digest if it is not yet known.
    # Todo: Can we somehow factor this out into a separate (singleton) task,
    #     on which we wait?
    #     Waiting synchronously is not a good idea, since we would be holding
    #     the worker process, but I think retrying after some countdown would
    #     be the solution?
    #     self.apply_async(countdown=SOME_CONFIGURATION_VARIABLE)
    if not data_source.checksum:
        with data_source.data() as data:
            data_source.checksum, data_source.records = digest(data)
        db.session.commit()

    # Check if checksum is not in imported data sources.
    if DataSource.query.filter_by(checksum=data_source.checksum
                                  ).join(Variation).filter_by(task_done=True
                                                              ).count() > 0:
        raise TaskError('duplicate_data_source',
                        'Identical data source already imported')

    def delete_observations():
        variation.observations.delete()
        db.session.commit()
    current_task.register_cleanup(current_task.request.id,
                                  delete_observations)

    # In case we are retrying after a failed import, delete any existing
    # observations for this variation.
    delete_observations()

    try:
        data = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    # Remember that this only makes sense if autocommit and autoflush are off,
    # which is the default for flask-sqlalchemy.
    # Related discussion: https://groups.google.com/forum/?fromgroups=#!topic/sqlalchemy/ZD5RNfsmQmU

    # Alternative solution might be to dump all observations to a file and
    # import from that. It would not have memory problems and is probably
    # faster, but really not portable.
    # A better option is probably to bypass part of the ORM like discussed in
    # this presentation:
    #
    # https://speakerdeck.com/rwarren/a-brief-intro-to-profiling-in-python
    #
    # Not sure if this would solve any memory problems, but it's probably a
    # lot faster than what we do now.

    try:
        with data as observations:
            old_percentage = -1
            for i, (record, chromosome, position, reference, observed, zygosity, support) \
                    in enumerate(read_observations(observations,
                                                   filetype=data_source.filetype,
                                                   skip_filtered=variation.skip_filtered,
                                                   use_genotypes=variation.use_genotypes,
                                                   prefer_genotype_likelihoods=variation.prefer_genotype_likelihoods)):
                # Task progress is updated in whole percentages, so for a
                # maximum of 100 times per task.
                percentage = min(int(record / data_source.records * 100), 99)
                if percentage > old_percentage:
                    current_task.update_state(state='PROGRESS',
                                              meta={'percentage': percentage})
                    old_percentage = percentage
                observation = Observation(variation, chromosome, position,
                                          reference, observed,
                                          zygosity=zygosity, support=support)
                db.session.add(observation)
                if i % DB_BUFFER_SIZE == DB_BUFFER_SIZE - 1:
                    db.session.flush()
                    db.session.commit()
                    # Todo: In principle I think calling session.flush() once
                    #     every N records should work perfectly. We could then
                    #     just do a session.rollback() on error.
                    #     Unfortunately, session.flush() does not prevent the
                    #     memory usage from increasing (even with expire_all()
                    #     or expunge_all() calls). So in practice we cannot
                    #     use it (tested with psycopg2 2.4.5 and SQLAlchemy
                    #     0.7.8).
                    #     As an alternative, we call session.commit() but the
                    #     problem is that a simple session.rollback() is not
                    #     enough. Therefore we use the CleanTask base class
                    #     to register a cleanup handler.
    except ReadError as e:
        raise TaskError('invalid_observations', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    variation.task_done = True
    db.session.commit()

    logger.info('Finished task: import_variation(%d)', variation_id)


@celery.task(base=CleanTask)
def import_coverage(coverage_id):
    """
    Import coverage as regions.
    """
    logger.info('Started task: import_coverage(%d)', coverage_id)

    current_task.update_state(state='PROGRESS', meta={'percentage': 0})

    coverage = Coverage.query.get(coverage_id)
    if coverage is None:
        raise TaskError('coverage_not_found', 'Coverage not found')

    if coverage.task_done:
        raise TaskError('coverage_imported', 'Coverage already imported')

    if coverage.task_uuid and coverage.task_uuid != current_task.request.id:
        raise TaskError('coverage_importing', 'Coverage is being imported '
                        'by another task instance')

    data_source = coverage.data_source

    # Calculate data digest if it is not yet known.
    if not data_source.checksum:
        with data_source.data() as data:
            data_source.checksum, data_source.records = digest(data)
        db.session.commit()

    # Check if checksum is not in imported data sources.
    if DataSource.query.filter_by(checksum=data_source.checksum
                                  ).join(Coverage).filter_by(task_done=True
                                                             ).count() > 0:
        raise TaskError('duplicate_data_source',
                        'Identical data source already imported')

    def delete_regions():
        coverage.regions.delete()
        db.session.commit()
    current_task.register_cleanup(current_task.request.id, delete_regions)

    # In case we are retrying after a failed import, delete any existing
    # regions for this coverage.
    delete_regions()

    try:
        data = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    try:
        with data as regions:
            old_percentage = -1
            for i, (record, chromosome, begin, end) \
                    in enumerate(read_regions(regions,
                                              filetype=data_source.filetype)):
                percentage = min(int(record / data_source.records * 100), 99)
                if percentage > old_percentage:
                    current_task.update_state(state='PROGRESS',
                                              meta={'percentage': percentage})
                    old_percentage = percentage
                db.session.add(Region(coverage, chromosome, begin, end))
                if i % DB_BUFFER_SIZE == DB_BUFFER_SIZE - 1:
                    db.session.flush()
                    db.session.commit()
    except ReadError as e:
        raise TaskError('invalid_regions', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    coverage.task_done = True
    db.session.commit()

    logger.info('Finished task: import_coverage(%d)', coverage_id)


@celery.task(base=VardaTask)
def write_annotation(annotation_id):
    """
    Annotate variants with frequencies from the database.

    :arg annotation_id: Annotation to write.
    :type annotation_id: int
    """
    logger.info('Started task: write_annotation(%d)', annotation_id)

    current_task.update_state(state='PROGRESS', meta={'percentage': 0})

    annotation = Annotation.query.get(annotation_id)
    if annotation is None:
        raise TaskError('annotation_not_found', 'Annotation not found')

    if annotation.task_done:
        raise TaskError('annotation_written', 'Annotation already written')

    if annotation.task_uuid and annotation.task_uuid != current_task.request.id:
        raise TaskError('annotation_writing', 'Annotation is being written '
                        'by another task instance')

    original_data_source = annotation.original_data_source
    annotated_data_source = annotation.annotated_data_source

    # Calculate data digest if it is not yet known.
    if not original_data_source.checksum:
        with original_data_source.data() as data:
            (original_data_source.checksum,
             original_data_source.records) = digest(data)
        db.session.commit()

    try:
        original_data = original_data_source.data()
        annotated_data = annotated_data_source.data_writer()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    try:
        with original_data as original, \
                annotated_data as annotated_variants:
            annotate_data_source(original, annotated_variants,
                                 original_filetype=original_data_source.filetype,
                                 annotated_filetype=annotated_data_source.filetype,
                                 queries=annotation.queries,
                                 original_records=original_data_source.records)
    except ReadError as e:
        annotated_data_source.empty()
        raise TaskError('invalid_data_source', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    annotation.task_done = True
    db.session.commit()

    logger.info('Finished task: write_annotation(%d)', annotation_id)


@celery.task(base=VardaTask)
def ping():
    """
    Ping-pong task useful for testing purposes.
    """
    logger.info('Started task: ping')
    logger.info('Finished task: ping')
    return 'pong'
