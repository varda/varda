"""
Celery tasks.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from __future__ import division

from collections import defaultdict
from contextlib import contextmanager
import hashlib
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
from .models import Annotation, Coverage, DataSource, DataUnavailable, Observation, Sample, Region, Variation
from .region_binning import all_bins
from .utils import digest, normalize_variant, normalize_chromosome, normalize_region, ReferenceMismatch


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


def annotate_variants(original_variants, annotated_variants, original_filetype='vcf', annotated_filetype='vcf', exclude_sample_ids=None, include_sample_ids=None, original_records=1):
    """
    Annotate variants.
    """
    exclude_sample_ids = exclude_sample_ids or []
    include_sample_ids = include_sample_ids or {}

    if original_filetype != 'vcf':
        raise ReadError('Original data must be in VCF format')

    if annotated_filetype != 'vcf':
        raise ReadError('Annotated data must be in VCF format')

    reader = vcf.Reader(original_variants)

    # Number of lines read (i.e. comparable to what is reported by
    # ``varda.utils.digest``).
    current_record = len(reader._header_lines) + 1

    reader.infos['VARDA_FREQ'] = VcfInfo('VARDA_FREQ', vcf_field_counts['A'], 'Float',
        'Frequency in Varda (over %i samples)' % Sample.query.filter_by(coverage_profile=True).filter(~Sample.id.in_(exclude_sample_ids)).count())
    for label in include_sample_ids:
        reader.infos['%s_FREQ' % label] = VcfInfo('%s_FREQ' % label, vcf_field_counts['A'], 'Float',
                                                   'Frequency in %s' % label)
    writer = vcf.Writer(annotated_variants, reader, lineterminator='\n')

    old_percentage = -1
    for record in reader:
        current_record += 1
        percentage = min(int(current_record / original_records * 100), 99)
        if percentage > old_percentage:
            current_task.update_state(state='PROGRESS', meta={'percentage': percentage})
            old_percentage = percentage

        frequencies = []
        sample_frequencies = {label: [] for label in include_sample_ids}
        for index, allele in enumerate(record.ALT):
            try:
                chromosome, position, reference, observed = normalize_variant(record.CHROM, record.POS, record.REF, str(allele))
            except ReferenceMismatch as e:
                raise ReadError(str(e))

            end_position = position + max(1, len(reference)) - 1
            bins = all_bins(position, end_position)

            # Todo: Check if we handle pooled samples correctly.
            # Todo: Only count activated samples.

            # Frequency over entire database, except:
            #  - samples in ``exclude_sample_ids``
            #  - samples without coverage profile
            observations = Observation.query.filter_by(chromosome=chromosome,
                                                       position=position,
                                                       reference=reference,
                                                       observed=observed).join(Variation).filter(~Variation.sample_id.in_(exclude_sample_ids)).join(Sample).filter_by(coverage_profile=True).count()
            coverage = Region.query.join(Coverage).filter(Region.chromosome == chromosome,
                                                          Region.begin <= position,
                                                          Region.end >= end_position,
                                                          Region.bin.in_(bins),
                                                          ~Coverage.sample_id.in_(exclude_sample_ids)).count()
            assert observations <= coverage
            if coverage:
                frequencies.append(observations / coverage)
            else:
                frequencies.append(0)

            # Frequency for each sample in ``include_sample_ids``.
            # Todo: This list has to be filtered for samples that are public
            #     or the user is owner of.
            for label, sample_id in include_sample_ids.items():
                observations = Observation.query.filter_by(chromosome=chromosome,
                                                           position=position,
                                                           reference=reference,
                                                           observed=observed).join(Variation).filter_by(sample_id=sample_id).count()
                coverage = Region.query.join(Coverage).filter(Region.chromosome == chromosome,
                                                              Region.begin <= position,
                                                              Region.end >= end_position,
                                                              Region.bin.in_(bins),
                                                              Coverage.sample_id == sample_id).count()
                # Todo: We'd better just check for sample.coverage_profile.
                if not coverage:
                    coverage = Sample.get(sample_id).pool_size
                assert observations <= coverage
                if coverage:
                    sample_frequencies[label].append(observations / coverage)
                else:
                    sample_frequencies[label].append(0)

        record.add_info('VARDA_FREQ', frequencies)
        for label in include_sample_ids:
            record.add_info('%s_FREQ' % label, sample_frequencies[label])
        writer.write_record(record)


def read_observations(observations, filetype='vcf'):
    if filetype != 'vcf':
        raise ReadError('Data must be in VCF format')

    reader = vcf.Reader(observations)

    # Number of lines read (i.e. comparable to what is reported by
    # ``varda.utils.digest``).
    current_record = len(reader._header_lines) + 1

    for record in reader:
        current_record += 1

        if 'SV' in record.INFO:
            # For now we ignore these, reference is likely to be larger than
            # the maximum of 200 by the database schema.
            # Example use of this type are large deletions in 1000 Genomes.
            continue

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

            # Variant support is defined by the number of samples in which a
            # variant allele was called, ignoring homo-/heterozygocity.
            # Todo: This check can break if index > 9.
            try:
                support = sum(1 for sample in record.samples if str(index + 1) in sample['GT'])
            except AttributeError:
                support = 1

            #if 'SF' in record.INFO and False:
            #    # Todo: Per alt allele?
            #    support = len(record.INFO['SF'])
            #elif 'AC' in record.INFO and False:
            #    # Todo: Per alt allele?
            #    support = record.INFO['AC'][0]
            #else:
            #    support = 1

            yield current_record, chromosome, position, reference, observed, support


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

    variation = Variation.query.get(variation_id)
    if variation is None:
        raise TaskError('variation_not_found', 'Variation not found')

    if variation.imported:
        raise TaskError('variation_imported', 'Variation already imported')

    if variation.import_task_uuid:
        # Note: This check if the importing task is still running is perhaps
        #     not waterproof (I think PENDING is also reported for unknown
        #     tasks, and they might be unknown after a while).
        #     It can be the case that the task was aborted. In that case, the
        #     uuid is still set (needed to retrieve the error state), but a
        #     new import task can be started.
        #     See also: http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists
        result = import_variation.AsyncResult(variation.import_task_uuid)
        if result.state in ('PENDING', 'STARTED', 'PROGRESS'):
            raise TaskError('variation_importing', 'Variation is being imported')

    # Todo: This has a possible race condition, but I'm not bothered to fix it
    #     at the moment. Reading and setting import_task_uuid should be an
    #     atomic action.
    variation.import_task_uuid = current_task.request.id
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
    if DataSource.query.filter_by(checksum=data_source.checksum).join(Variation).filter_by(imported=True).count() > 0:
        raise TaskError('duplicate_data_source', 'Identical data source already imported')

    def delete_observations():
        variation.observations.delete()
        db.session.commit()
    current_task.register_cleanup(current_task.request.id, delete_observations)

    try:
        data = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    # Remember that this only makes sence if autocommit and autoflush are off,
    # which is the default for flask-sqlalchemy.
    # Related discussion: https://groups.google.com/forum/?fromgroups=#!topic/sqlalchemy/ZD5RNfsmQmU

    # Alternative solution might be to dump all observations to a file and
    # import from that. It would not have memory problems and is probably
    # faster, but really not portable.

    try:
        with data as observations:
            old_percentage = -1
            for i, (record, chromosome, position, reference, observed, support) in enumerate(read_observations(observations, filetype=data_source.filetype)):
                # Task progress is updated in whole percentages, so for a
                # maximum of 100 times per task.
                percentage = min(int(record / data_source.records * 100), 99)
                if percentage > old_percentage:
                    current_task.update_state(state='PROGRESS', meta={'percentage': percentage})
                    old_percentage = percentage
                observation = Observation(variation, chromosome, position, reference, observed, support=support)
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
    variation.imported = True
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

    if coverage.imported:
        raise TaskError('coverage_imported', 'Coverage already imported')

    if coverage.import_task_uuid:
        result = import_coverage.AsyncResult(coverage.import_task_uuid)
        if result.state in ('PENDING', 'STARTED', 'PROGRESS'):
            raise TaskError('coverage_importing', 'Coverage is being imported')

    coverage.import_task_uuid = current_task.request.id
    db.session.commit()

    data_source = coverage.data_source

    # Calculate data digest if it is not yet known.
    if not data_source.checksum:
        with data_source.data() as data:
            data_source.checksum, data_source.records = digest(data)
        db.session.commit()

    # Check if checksum is not in imported data sources.
    if DataSource.query.filter_by(checksum=data_source.checksum).join(Coverage).filter_by(imported=True).count() > 0:
        raise TaskError('duplicate_data_source', 'Identical data source already imported')

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
            for i, (record, chromosome, begin, end) in enumerate(read_regions(regions, filetype=data_source.filetype)):
                percentage = min(int(record / data_source.records * 100), 99)
                if percentage > old_percentage:
                    current_task.update_state(state='PROGRESS', meta={'percentage': percentage})
                    old_percentage = percentage
                db.session.add(Region(coverage, chromosome, begin, end))
                if i % DB_BUFFER_SIZE == DB_BUFFER_SIZE - 1:
                    db.session.commit()
    except ReadError as e:
        raise TaskError('invalid_regions', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    coverage.imported = True
    db.session.commit()

    logger.info('Finished task: import_coverage(%d)', coverage_id)


@celery.task
def write_annotation(annotation_id, exclude_sample_ids=None, include_sample_ids=None):
    """
    Annotate variants with frequencies from the database.
    """
    logger.info('Started task: write_annotation(%d)', annotation_id)

    exclude_sample_ids = exclude_sample_ids or []
    include_sample_ids = include_sample_ids or {}

    annotation = Annotation.query.get(annotation_id)
    if annotation is None:
        raise TaskError('annotation_not_found', 'Annotation not found')

    if annotation.written:
        raise TaskError('annotation_written', 'Annotation already written')

    if annotation.write_task_uuid:
        result = write_annotation.AsyncResult(annotation.write_task_uuid)
        if result.state in ('PENDING', 'STARTED', 'PROGRESS'):
            raise TaskError('annotation_writing', 'Annotation is being written')

    annotation.write_task_uuid = current_task.request.id
    db.session.commit()

    original_data_source = annotation.original_data_source
    annotated_data_source = annotation.annotated_data_source

    # Calculate data digest if it is not yet known.
    if not original_data_source.checksum:
        with original_data_source.data() as data:
            original_data_source.checksum, original_data_source.records = digest(data)
        db.session.commit()

    try:
        original_data = original_data_source.data()
        annotated_data = annotated_data_source.data_writer()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    try:
        with original_data as original_variants, annotated_data as annotated_variants:
            annotate_variants(original_variants, annotated_variants,
                              original_filetype=original_data_source.filetype,
                              annotated_filetype=annotated_data_source.filetype,
                              exclude_sample_ids=exclude_sample_ids,
                              include_sample_ids=include_sample_ids,
                              original_records=original_data_source.records)
    except ReadError as e:
        annotated_data_source.empty()
        raise TaskError('invalid_observations', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    annotation.written = True
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
