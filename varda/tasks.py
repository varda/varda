"""
Celery tasks.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from __future__ import division

from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import itertools
import os
import time
import uuid

from celery import current_task, current_app, Task
from celery.utils.log import get_task_logger
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


class CleanTask(Task):
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


def annotate_variants(original_variants, annotated_variants,
                      original_filetype='vcf', annotated_filetype='vcf',
                      global_frequency=True, sample_frequency=None,
                      exclude=None, original_records=1):
    """
    Read variants from a file and write them to another file with annotation.

    :arg original_variants: Open handle to a file with variants.
    :type observations: file-like object
    :arg annotated_variants: Open handle to write annotated variants to.
    :type observations: file-like object
    :kwarg original_filetype: Filetype for variants (currently only ``vcf``
        allowed).
    :type filetype: str
    :kwarg annotated_filetype: Filetype for annotated variants (currently only
        ``vcf`` allowed).
    :type filetype: str
    :arg global_frequencies: Whether or not to compute global frequencies.
    :type global_frequencies: bool
    :arg local_frequencies: List of (`label`, `sample`) tuples to compute
        frequencies for.
    :type local_frequencies: list of (str, Sample)
    :arg exclude: List of samples to exclude from frequency calculations.
    :type exclude: list of Sample
    :arg original_records: Number of records in original variants file.
    :type original_records: int
    """
    # Todo: Here we should check again if the samples we use are active, since
    #     it could be a long time ago when this task was submitted.
    sample_frequency = sample_frequency or []
    exclude = exclude or []

    if original_filetype != 'vcf':
        raise ReadError('Original data must be in VCF format')

    if annotated_filetype != 'vcf':
        raise ReadError('Annotated data must be in VCF format')

    reader = vcf.Reader(original_variants)

    # Header line in VCF output for global frequencies.
    if global_frequency:
        reader.infos['VARDA_FREQ'] = VcfInfo(
            'VARDA_FREQ', vcf_field_counts['A'], 'Float',
            'Frequency in Varda (over %i samples, using coverage profiles)'
            % Sample.query.filter_by(active=True,
                                     coverage_profile=True).filter(
                ~Sample.id.in_([s.id for s in exclude])).count())

    # Todo: We have to refer to the samples in the VCF file by some label,
    #     ideally consisting of only uppercase letters. For now, we just
    #     generate some random labels, but we might let the user define them
    #     in the future.
    labels = ['VARDA_FREQ_' + chr(x) for x, _ in
              zip(itertools.count(ord('A')), sample_frequency)]

    # Header lines in VCF output for sample frequencies.
    for sample, label in zip(sample_frequency, labels):
        reader.infos[label] = VcfInfo(
            label, vcf_field_counts['A'], 'Float',
            'Frequency in %s (over %i samples, %susing coverage profiles)'
            % (sample.name, sample.pool_size,
               '' if sample.coverage_profile else 'not '))

    writer = vcf.Writer(annotated_variants, reader, lineterminator='\n')

    # Number of lines read (i.e. comparable to what is reported by
    # ``varda.utils.digest``).
    current_record = len(reader._header_lines) + 1

    old_percentage = -1
    for record in reader:
        current_record += 1
        percentage = min(int(current_record / original_records * 100), 99)
        if percentage > old_percentage:
            current_task.update_state(state='PROGRESS',
                                      meta={'percentage': percentage})
            old_percentage = percentage

        global_frequencies = []
        sample_frequencies = [[] for _ in sample_frequency]
        for index, allele in enumerate(record.ALT):
            try:
                chromosome, position, reference, observed = normalize_variant(
                    record.CHROM, record.POS, record.REF, str(allele))
            except ReferenceMismatch as e:
                raise ReadError(str(e))

            global_frequency_result, sample_frequency_result = calculate_frequency(
                chromosome, position, reference, observed, global_frequency,
                sample_frequency, exclude)
            if global_frequency_result is not None:
                global_frequencies.append(global_frequency_result)
            if sample_frequency_result is not None:
                for i, f in enumerate(sample_frequency_result):
                    sample_frequencies[i].append(f)

        if global_frequency:
            record.add_info('VARDA_FREQ', global_frequencies)
        for fs, label in zip(sample_frequencies, labels):
            record.add_info(label, fs)
        writer.write_record(record)


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
    :kwarg use_genotypes: Whether or not to use genotypes (if available) for
        allele counts.
    :type use_genotypes: bool
    :kwarg prefer_genotype_likelihoods: Whether or not to prefer deriving
        genotypes from likelihoods (if available).
    :type prefer_genotype_likelihoods: bool

    :return: Generator yielding tuples (current_record, chromosome, position,
        reference, observed, alleles, support).
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

        # For each ALT, store sample count per number of supporting alleles.
        # This generalizes zygosity, but for diploid genomes this will be
        # something like:
        #
        #     allele_support =
        #         [{1: 327, 2: 7},     # First ALT, 327 het, 7 hom
        #          {1: 73},            # Second ALT, 73 het, 0 hom
        #          {1: 154, 2: 561}]   # Third ALT, 154 het, 561 hom
        #
        # The None value is used for the unknown genotype.
        allele_support = [Counter() for _ in record.ALT]

        # In the case where we don't have genotypes or don't want to use them,
        # we just count the number of samples and store an unknown number of
        # alleles. But only if there is exactly one ALT.

        if use_genotypes:
            for call in record.samples:
                try:
                    genotype = read_genotype(call, prefer_genotype_likelihoods)
                except NoGenotypesInRecord:
                    # Exception will be raised for all calls in this record,
                    # so we can define the aggregate result and break.
                    if len(record.ALT) == 1:
                        allele_support = [{None: len(record.samples)}]
                    break

                if genotype:
                    counts = Counter(a - 1 for a in genotype if a > 0)
                    for index, count in counts.items():
                        allele_support[index][count] += 1

        elif len(record.ALT) == 1:
            allele_support = [{None: len(record.samples)}]

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

            for alleles, support in allele_support[index].items():
                yield (current_record, chromosome, position, reference,
                       observed, alleles, support)


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
        yield current_record, chromosome, begin + 1, end


@celery.task(base=CleanTask)
def import_variation(variation_id):
    """
    Import variation as observations.
    """
    logger.info('Started task: import_variation(%d)', variation_id)

    # Todo: Keep a record in the database of the import parameters (ok, we
    #     don't have any yet, but we probably will).

    variation = Variation.query.get(variation_id)
    if variation is None:
        raise TaskError('variation_not_found', 'Variation not found')

    if variation.task_done:
        raise TaskError('variation_imported', 'Variation already imported')

    if variation.task_uuid:
        # Note: This check if the importing task is still running is perhaps
        #     not waterproof (I think PENDING is also reported for unknown
        #     tasks, and they might be unknown after a while).
        #     It can be the case that the task was aborted. In that case, the
        #     uuid is still set (needed to retrieve the error state), but a
        #     new import task can be started.
        #     See also: http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists
        result = import_variation.AsyncResult(variation.task_uuid)
        if result.state in ('PENDING', 'STARTED', 'PROGRESS'):
            raise TaskError('variation_importing',
                            'Variation is being imported')

    # Todo: This has a possible race condition, but I'm not bothered to fix it
    #     at the moment. Reading and setting import_task_uuid should be an
    #     atomic action.
    variation.task_uuid = current_task.request.id
    db.session.commit()

    data_source = variation.data_source

    # Calculate data digest if it is not yet known.
    # Todo: Can we somehow factor this out into a separate (singleton) task,
    #     on which we wait?
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

    try:
        with data as observations:
            old_percentage = -1
            for i, (record, chromosome, position, reference, observed, alleles, support) \
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
                                          alleles=alleles, support=support)
                db.session.add(observation)
                if i % DB_BUFFER_SIZE == DB_BUFFER_SIZE - 1:
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

    coverage = Coverage.query.get(coverage_id)
    if coverage is None:
        raise TaskError('coverage_not_found', 'Coverage not found')

    if coverage.task_done:
        raise TaskError('coverage_imported', 'Coverage already imported')

    if coverage.task_uuid:
        result = import_coverage.AsyncResult(coverage.task_uuid)
        if result.state in ('PENDING', 'STARTED', 'PROGRESS'):
            raise TaskError('coverage_importing',
                            'Coverage is being imported')

    coverage.task_uuid = current_task.request.id
    db.session.commit()

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
                    db.session.commit()
    except ReadError as e:
        raise TaskError('invalid_regions', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    coverage.task_done = True
    db.session.commit()

    logger.info('Finished task: import_coverage(%d)', coverage_id)


@celery.task
def write_annotation(annotation_id):
    """
    Annotate variants with frequencies from the database.

    :arg annotation_id: Annotation to write.
    :type annotation_id: int
    """
    logger.info('Started task: write_annotation(%d)', annotation_id)

    annotation = Annotation.query.get(annotation_id)
    if annotation is None:
        raise TaskError('annotation_not_found', 'Annotation not found')

    if annotation.task_done:
        raise TaskError('annotation_written', 'Annotation already written')

    if annotation.task_uuid:
        result = write_annotation.AsyncResult(annotation.task_uuid)
        if result.state in ('PENDING', 'STARTED', 'PROGRESS'):
            raise TaskError('annotation_writing',
                            'Annotation is being written')

    annotation.task_uuid = current_task.request.id
    db.session.commit()

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
        with original_data as original_variants, \
                annotated_data as annotated_variants:
            annotate_variants(original_variants, annotated_variants,
                              original_filetype=original_data_source.filetype,
                              annotated_filetype=annotated_data_source.filetype,
                              global_frequency=annotation.global_frequency,
                              sample_frequency=annotation.sample_frequency,
                              exclude=annotation.exclude,
                              original_records=original_data_source.records)
    except ReadError as e:
        annotated_data_source.empty()
        raise TaskError('invalid_observations', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    annotation.task_done = True
    db.session.commit()

    logger.info('Finished task: write_annotation(%d)', annotation_id)


@celery.task
def ping():
    """
    Ping-pong task usefull for testing purposes.
    """
    logger.info('Started task: ping')
    logger.info('Finished task: ping')
    return 'pong'
