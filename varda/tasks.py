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
from .models import Annotation, Coverage, DataSource, DataUnavailable, Observation, Sample, Region, Variant, Variation
from .region_binning import all_bins
from .utils import digest, normalize_variant, normalize_chromosome, normalize_region, ReferenceMismatch


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


def annotate_variants(original_variants, annotated_variants, original_filetype='vcf', annotated_filetype='vcf', ignore_sample_ids=None, original_records=1):
    """
    .. todo:: Merge back population study annotation (see implementation in
        the old-population-study branch).

    .. todo:: Calculate frequencies instead of counts, and take chromosome
        into account (config.CHROMOSOMES).
    """
    ignore_sample_ids = ignore_sample_ids or []

    if original_filetype != 'vcf':
        raise ReadError('Original data must be in VCF format')

    if annotated_filetype != 'vcf':
        raise ReadError('Annotated data must be in VCF format')

    reader = vcf.Reader(original_variants)

    reader.infos['OBS'] = VcfInfo('OBS', vcf_field_counts['A'], 'Integer',
        'Samples with variant (out of %i)' % Sample.query.count())
    reader.infos['COV'] = VcfInfo('COV', vcf_field_counts['A'], 'Integer',
        'Samples with coverage (out of %i)' % Sample.query.count())
    writer = vcf.Writer(annotated_variants, reader, lineterminator='\n')

    old_percentage = -1
    for i, record in enumerate(reader):
        # Task progress is updated in whole percentages, so for a maximum of
        # 100 times per task.
        percentage = min(int(i / original_records * 100), 99)
        if percentage > old_percentage:
            current_task.update_state(state='PROGRESS', meta={'percentage': percentage})
            old_percentage = percentage

        observations = []
        coverage = []
        for index, allele in enumerate(record.ALT):
            try:
                chromosome, position, reference, observed = normalize_variant(record.CHROM, record.POS, record.REF, str(allele))
            except ReferenceMismatch as e:
                raise ReadError(str(e))

            end_position = position + max(1, len(reference)) - 1
            bins = all_bins(position, end_position)

            try:
                variant = Variant.query.filter_by(chromosome=chromosome, position=position, reference=reference, observed=observed).one()
                observations.append(variant.observations.join(Variation).filter(~Variation.sample_id.in_(ignore_sample_ids)).count())
            except NoResultFound:
                observations.append(0)
            coverage.append(Region.query.join(Coverage).filter(Region.chromosome == chromosome,
                                                               Region.begin <= position,
                                                               Region.end >= end_position,
                                                               Region.bin.in_(bins),
                                                               ~Coverage.sample_id.in_(ignore_sample_ids)).count())

        record.add_info('OBS', observations)
        record.add_info('COV', coverage)
        writer.write_record(record)


def read_observations(observations, filetype='vcf'):
    # Todo: Merge back population study importing (see implementation in the
    #     old-population-study branch).
    if filetype != 'vcf':
        raise ReadError('Data must be in VCF format')

    reader = vcf.Reader(observations)

    for record in reader:
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

            # Variant support is defined by the number of samples in which a
            # variant allele was called, ignoring homo-/heterozygocity.
            # Todo: This check can break if index > 9.
            support = sum(1 for sample in record.samples if str(index + 1) in sample['GT'])

            #if 'SF' in record.INFO and False:
            #    # Todo: Per alt allele?
            #    support = len(record.INFO['SF'])
            #elif 'AC' in record.INFO and False:
            #    # Todo: Per alt allele?
            #    support = record.INFO['AC'][0]
            #else:
            #    support = 1

            yield chromosome, position, reference, observed, support


def read_regions(regions, filetype='bed'):
    # Todo: Use pybedtools to parse BED file?
    if filetype != 'bed':
        raise ReadError('Data must be in BED format')

    for line in regions:
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
        yield chromosome, begin + 1, end


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
        # Todo: Check somehow if the importing task is still running.
        # http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists
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

    # Note: Since we are dealing with huge numbers of entries here, we commit
    # after each INSERT and manually rollback. Using builtin session rollback
    # would fill up all our memory.
    def delete_observations():
        variation.observations.delete()
        db.session.commit()
    current_task.register_cleanup(current_task.request.id, delete_observations)

    try:
        data = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    with data as observations:
        try:
            old_percentage = -1
            for i, (chromosome, position, reference, observed, support) in enumerate(read_observations(observations, filetype=data_source.filetype)):
                # Task progress is updated in whole percentages, so for a
                # maximum of 100 times per task.
                percentage = min(int(i / data_source.records * 100), 99)
                if percentage > old_percentage:
                    current_task.update_state(state='PROGRESS', meta={'percentage': percentage})
                    old_percentage = percentage
                    time.sleep(1)
                # SQLAlchemy doesn't seem to have anything like INSERT IGNORE
                # or INSERT ... ON DUPLICATE KEY UPDATE, so we have to work
                # our way around the situation.
                try:
                    # Todo: Check for errors (binning on begin/end may fail,
                    #     sequences might be too long).
                    variant = Variant(chromosome, position, reference, observed)
                    db.session.add(variant)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    try:
                        variant = Variant.query.filter_by(chromosome=chromosome, position=position, reference=reference, observed=observed).one()
                    except NoResultFound:
                        # Should never happen.
                        raise TaskError('database_inconsistency', 'Unrecoverable inconsistency of the database observed')
                observation = Observation(variant, variation, support=support)
                db.session.add(observation)
                db.session.commit()
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

    if coverage.import_task_uuid is not None:
        # Todo: Check somehow if the importing task is still running.
        # http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists
        raise TaskError('coverage_importing', 'Coverage is being imported')

    # Todo: This has a possible race condition, but I'm not bothered to fix it
    #     at the moment. Reading and setting import_task_uuid should be an
    #     atomic action.
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

    try:
        data = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    # Note: Since we are dealing with huge numbers of entries here, we commit
    # after each INSERT and manually rollback. Using builtin session rollback
    # would fill up all our memory.
    def delete_regions():
        coverage.regions.delete()
        db.session.commit()
    current_task.register_cleanup(current_task.request.id, delete_regions)

    with data as regions:
        try:
            old_percentage = -1
            for i, (chromosome, begin, end) in enumerate(read_regions(regions, filetype=data_source.filetype)):
                # Task progress is updated in whole percentages, so for a
                # maximum of 100 times per task.
                percentage = min(int(i / data_source.records * 100), 99)
                if percentage > old_percentage:
                    current_task.update_state(state='PROGRESS', meta={'percentage': percentage})
                    old_percentage = percentage
                db.session.add(Region(coverage, chromosome, begin, end))
                db.session.commit()
        except ReadError as e:
            raise TaskError('invalid_regions', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    coverage.imported = True
    db.session.commit()

    logger.info('Finished task: import_coverage(%d)', coverage_id)


@celery.task(base=CleanTask)
def write_annotation(annotation_id, ignore_sample_ids=None):
    """
    Annotate variants with frequencies from the database.
    """
    logger.info('Started task: write_annotation(%d)', annotation_id)

    ignore_sample_ids = ignore_sample_ids or []

    annotation = Annotation.query.get(annotation_id)
    if annotation is None:
        raise TaskError('annotation_not_found', 'Annotation not found')

    if annotation.written:
        raise TaskError('annotation_written', 'Annotation already written')

    if annotation.write_task_uuid is not None:
        # Todo: Check somehow if the writing task is still running, it might
        #     also be a failed task.
        # http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists
        raise TaskError('annotation_writing', 'Annotation is being written')

    # Todo: This has a possible race condition, but I'm not bothered to fix it
    #     at the moment. Reading and setting write_task_uuid should be an
    #     atomic action.
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

    with original_data as original_variants, annotated_data as annotated_variants:
        try:
            annotate_variants(original_variants, annotated_variants,
                              original_filetype=original_data_source.filetype,
                              annotated_filetype=annotated_data_source.filetype,
                              ignore_sample_ids=ignore_sample_ids,
                              original_records=original_data_source.records)
        except ReadError as e:
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
