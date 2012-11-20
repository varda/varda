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


FLUSH_COUNT = 1000


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

    # Number of lines read (i.e. comparable to what is reported by
    # ``varda.utils.digest``).
    current_record = len(reader._header_lines) + 1

    reader.infos['OBS'] = VcfInfo('OBS', vcf_field_counts['A'], 'Integer',
        'Samples with variant (out of %i)' % Sample.query.count())
    reader.infos['COV'] = VcfInfo('COV', vcf_field_counts['A'], 'Integer',
        'Samples with coverage (out of %i)' % Sample.query.count())
    writer = vcf.Writer(annotated_variants, reader, lineterminator='\n')

    old_percentage = -1
    for record in reader:
        current_record += 1
        percentage = min(int(current_record / original_records * 100), 99)
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

            observations.append(Observation.query.filter_by(chromosome=chromosome, position=position, reference=reference, observed=observed).join(Variation).filter(~Variation.sample_id.in_(ignore_sample_ids)).count())
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
    # Todo: Use pybedtools to parse BED file?
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


@celery.task
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
        # Todo: Check somehow if the importing task is still running. It can
        #     be the case that the task was aborted. In that case, the uuid
        #     is still set (to be able to retrieve the error state), but a
        #     new import task can be started.
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

    try:
        data = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    # Remember that this only makes sence if autocommit and autoflush are off,
    # which is the default for flask-sqlalchemy.
    # Related discussion:
    # https://groups.google.com/forum/?fromgroups=#!topic/sqlalchemy/ZD5RNfsmQmU

    # Alternative solution might be to dump all observations to a file and
    # import from that. It would not have memory problems and is probably
    # faster, but really not portable.

    with data as observations:
        try:
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
                if i % FLUSH_COUNT == FLUSH_COUNT - 1:
                    db.session.flush()
                    # Todo: I don't understand why memory usage keeps growing
                    #     during the entire import process. Even the following
                    #     don't help after the flush:
                    #     - db.session.expire_all()
                    #     - db.session.expunge_all()
                    #     CPython makes things worse by never giving garbage
                    #     collected memory back to the OS, so after a task has
                    #     had high memory usage it never goes down. A fix for
                    #     this is to always run the workers with
                    #     --maxtasksperchild=1.
        except ReadError as e:
            db.session.rollback()
            variation.import_task_uuid = None
            db.session.commit()
            raise TaskError('invalid_observations', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    variation.imported = True
    db.session.commit()

    logger.info('Finished task: import_variation(%d)', variation_id)


@celery.task
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

    try:
        data = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    with data as regions:
        try:
            old_percentage = -1
            for i, (record, chromosome, begin, end) in enumerate(read_regions(regions, filetype=data_source.filetype)):
                percentage = min(int(record / data_source.records * 100), 99)
                if percentage > old_percentage:
                    current_task.update_state(state='PROGRESS', meta={'percentage': percentage})
                    old_percentage = percentage
                db.session.add(Region(coverage, chromosome, begin, end))
                if i % FLUSH_COUNT == FLUSH_COUNT - 1:
                    db.session.flush()
        except ReadError as e:
            db.session.rollback()
            coverage.import_task_uuid = None
            db.session.commit()
            raise TaskError('invalid_regions', str(e))

    current_task.update_state(state='PROGRESS', meta={'percentage': 100})
    coverage.imported = True
    db.session.commit()

    logger.info('Finished task: import_coverage(%d)', coverage_id)


@celery.task
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

    with original_data as original_variants, annotated_data as annotated_variants:
        try:
            annotate_variants(original_variants, annotated_variants,
                              original_filetype=original_data_source.filetype,
                              annotated_filetype=annotated_data_source.filetype,
                              ignore_sample_ids=ignore_sample_ids,
                              original_records=original_data_source.records)
        except ReadError as e:
            # Todo: Empty annotated variants.
            annotation.write_task_uuid = None
            db.session.commit()
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
