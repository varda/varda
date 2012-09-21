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
import uuid

from celery import current_task, current_app, Task
from celery.utils.log import get_task_logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from vcf.parser import _Info as VcfInfo, field_counts as vcf_field_counts
from vcf.utils import trim_common_suffix
import vcf

from . import db, celery
from .models import Annotation, Coverage, DataSource, DataUnavailable, Observation, Sample, Region, Variant, Variation
from .region_binning import all_bins
from .utils import calculate_digest, normalize_chromosome


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


def annotate_variants(original_variants, annotated_variants, original_filetype='vcf', annotated_filetype='vcf', ignore_sample_ids=None):
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

    for record in reader:
        chrom = normalize_chromosome(record.CHROM)
        try:
            current_app.conf.CHROMOSOMES[chrom]
        except KeyError:
            raise ReadError('Chromosome "%s" not supported' % chrom)

        observations = []
        coverage = []
        for index, allele in enumerate(record.ALT):
            reference, allele = trim_common_suffix(record.REF.upper(),
                                                   str(allele).upper())
            if 'INDEL' in record.INFO and len(reference) >= len(allele):
                end = record.POS + len(reference) - 1
            else:
                end = record.POS
            bins = all_bins(record.POS, end)

            try:
                variant = Variant.query.filter_by(chromosome=chrom, begin=record.POS, end=end, reference=reference, variant=allele).one()
                observations.append(variant.observations.join(Variation).filter(~Variation.sample_id.in_(ignore_sample_ids)).count())
            except NoResultFound:
                observations.append(0)
            coverage.append(Region.query.join(Coverage).filter(Region.chromosome == chrom,
                                                               Region.begin <= record.POS,
                                                               Region.end >= end,
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
        chrom = normalize_chromosome(record.CHROM)
        try:
            current_app.conf.CHROMOSOMES[chrom]
        except KeyError:
            raise ReadError('Chromosome "%s" not supported' % chrom)

        # DP: Raw read depth.
        if 'DP4' not in record.INFO:
            coverage = record.INFO['DP']

            # AF: Allele Frequency, for each ALT allele, in the same order as
            # listed.
            if 'AF' in record.INFO:
                if isinstance(record.INFO['AF'], (list, tuple)):
                    # Todo: Shouldn't we use an AF record per allele?
                    support = coverage * record.INFO['AF'][0]
                else:
                    support = coverage * record.INFO['AF']
            # AF1: EM estimate of the site allele frequency of the strongest
            # non-reference allele.
            elif 'AF1' in record.INFO:
                support = coverage * record.INFO['AF1']
            else:
                raise TaskError('data_source_invalid',
                                'Cannot read variant support')

        else:
            # DP4: Number of 1) forward ref alleles; 2) reverse ref;
            # 3) forward non-ref; 4) reverse non-ref alleles, used in variant
            # calling. Sum can be smaller than DP because low-quality bases
            # are not counted.
            coverage = sum(record.INFO['DP4'])
            support = sum(record.INFO['DP4'][2:])

        for index, allele in enumerate(record.ALT):
            reference, allele = trim_common_suffix(record.REF.upper(),
                                                   str(allele).upper())
            if 'INDEL' in record.INFO and len(reference) >= len(allele):
                end = record.POS + len(reference) - 1
            else:
                end = record.POS

            # Todo: variant_coverage calculation is not correct with multiple
            #     non-ref alleles.
            yield chrom, record.POS, end, reference, allele, coverage, support // len(record.ALT)


def read_regions(regions, filetype='bed'):
    if filetype != 'bed':
        raise ReadError('Data must be in BED format')

    for line in regions:
        fields = line.split()
        if len(fields) < 1 or fields[0] == 'track':
            continue
        try:
            chromosome = normalize_chromosome(fields[0])
            begin = int(fields[1])
            end = int(fields[2])
        except (IndexError, ValueError):
            raise ReadError('Invalid line in BED file: "%s"' % line)
        try:
            current_app.conf.CHROMOSOMES[chromosome]
        except KeyError:
            raise ReadError('Chromosome "%s" not supported' % chromosome)
        yield chromosome, begin + 1, end


@celery.task(base=CleanTask)
def import_variation(variation_id):
    """
    Import variation as observations.

    .. todo:: Use `custom state <http://docs.celeryproject.org/en/latest/userguide/tasks.html#custom-states>`_
           to report progress.
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
    if not data_source.digest:
        data_source.digest = calculate_digest(data_source.data())
        db.session.commit()

    # Check if digest is not in imported data sources.
    if DataSource.query.filter_by(digest=data_source.digest).join(Variation).filter_by(imported=True).count() > 0:
        raise TaskError('duplicate_data_source', 'Identical data source already imported')

    try:
        data = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    # Note: Since we are dealing with huge numbers of entries here, we commit
    # after each INSERT and manually rollback. Using builtin session rollback
    # would fill up all our memory.
    def delete_observations():
        variation.observations.delete()
        db.session.commit()
    current_task.register_cleanup(current_task.request.id, delete_observations)

    with data as observations:
        try:
            for chromosome, begin, end, reference, variant_seq, total_coverage, variant_coverage in read_observations(observations, filetype=data_source.filetype):
                # SQLAlchemy doesn't seem to have anything like INSERT IGNORE
                # or INSERT ... ON DUPLICATE KEY UPDATE, so we have to work
                # our way around the situation.
                try:
                    variant = Variant(chromosome, begin, end, reference, variant_seq)
                    db.session.add(variant)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    try:
                        variant = Variant.query.filter_by(chromosome=chromosome, begin=begin, end=end, reference=reference, variant=variant_seq).one()
                    except NoResultFound:
                        # Should never happen.
                        raise TaskError('database_inconsistency', 'Unrecoverable inconsistency of the database observed')
                observation = Observation(variant, variation, total_coverage=total_coverage, variant_coverage=variant_coverage)
                db.session.add(observation)
                db.session.commit()
        except ReadError as e:
            raise TaskError('invalid_observations', str(e))

    variation.imported = True
    db.session.commit()

    logger.info('Finished task: import_variation(%d)', variation_id)


@celery.task(base=CleanTask)
def import_coverage(coverage_id):
    """
    Import coverage as regions.

    .. todo:: Use `custom state <http://docs.celeryproject.org/en/latest/userguide/tasks.html#custom-states>`_
           to report progress.
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
    if not data_source.digest:
        data_source.digest = calculate_digest(data_source.data())
        db.session.commit()

    # Check if digest is not in imported data sources.
    if DataSource.query.filter_by(digest=data_source.digest).join(Coverage).filter_by(imported=True).count() > 0:
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
            for chromosome, begin, end in read_regions(regions, filetype=data_source.filetype):
                db.session.add(Region(coverage, chromosome, begin, end))
                db.session.commit()
        except ReadError as e:
            raise TaskError('invalid_regions', str(e))

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

    try:
        original_data = annotation.original_data_source.data()
        annotated_data = annotation.annotated_data_source.data_writer()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    with original_data as original_variants, annotated_data as annotated_variants:
        try:
            annotate_variants(original_variants, annotated_variants,
                              original_filetype=annotation.original_data_source.filetype,
                              annotated_filetype=annotation.annotated_data_source.filetype,
                              ignore_sample_ids=ignore_sample_ids)
        except ReadError as e:
            raise TaskError('invalid_observations', str(e))

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
