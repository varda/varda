"""
Celery tasks.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from __future__ import division

from contextlib import contextmanager
import os
import uuid

from celery.utils.log import get_task_logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from vcf.parser import _Info as VcfInfo, field_counts as vcf_field_counts
from vcf.utils import trim_common_suffix
import vcf

from . import db, celery
from .models import Annotation, DataSource, DataUnavailable, Observation, Sample, Region, Variant
from .region_binning import all_bins


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
        super(Exception, self).__init__(code, message)


def normalize_chromosome(chromosome):
    """
    .. todo:: This should be in util.py or something.
    """
    if chromosome.startswith('NC_012920'):
        return 'M'
    if chromosome.startswith('chr'):
        return chromosome[3:]
    return chromosome


@contextmanager
def database_task(cleanup=None):
    """
    Context manager for a Celery task using the database.

    Upon closing, the database session is committed and if a
    :exc:`TaskError` was raised, the cleanup function argument is called
    first.

    .. todo:: We might add a setup function as argument.
    """
    try:
        yield
    except TaskError:
        if cleanup is not None:
            cleanup()
        raise
    finally:
        db.session.commit()


def _write_annotation(vcf, annotation, ignore_sample_ids=None):
    """
    .. todo:: Instead of reading from an open VCF, read from an abstracted
        variant reader.

    .. todo:: Merge back population study annotation (see implementation in
        the old-population-study branch).

    .. todo:: Use support field (and possibly total_coverage,
        variant_coverage) for population studies.
    """
    ignore_sample_ids = ignore_sample_ids or []

    reader = pyvcf.Reader(vcf)

    reader.infos['OBS'] = VcfInfo('OBS', vcf_field_counts['A'], 'Integer',
        'Samples with variant (out of %i)' % Sample.query.count())
    reader.infos['COV'] = VcfInfo('COV', vcf_field_counts['A'], 'Integer',
        'Samples with coverage (out of %i)' % Sample.query.count())
    writer = pyvcf.Writer(annotation, reader, lineterminator='\n')

    for entry in reader:
        chrom = normalize_chromosome(entry.CHROM)

        observations = []
        coverage = []
        for index, allele in enumerate(entry.ALT):
            reference, allele = trim_common_suffix(entry.REF.upper(),
                                                   str(allele).upper())
            if 'INDEL' in entry.INFO and len(reference) >= len(allele):
                end = entry.POS + len(reference) - 1
            else:
                end = entry.POS
            bins = all_bins(entry.POS, end)

            try:
                variant = Variant.query.filter_by(chromosome=chrom, begin=entry.POS, end=end, reference=reference, variant=allele).one()
                observations.append(variant.observations.join(DataSource).filter(~DataSource.sample_id.in_(ignore_sample_ids)).count())
            except NoResultFound:
                observations.append(0)
            coverage.append(Region.query.join(DataSource).filter(Region.chromosome == chrom,
                                                                 Region.begin <= entry.POS,
                                                                 Region.end >= end,
                                                                 Region.bin.in_(bins),
                                                                 ~DataSource.sample_id.in_(ignore_sample_ids)).count())

        entry.add_info('OBS', observations)
        entry.add_info('COV', coverage)
        writer.write_record(entry)


def read_observations(observations, filetype='vcf'):
    # Todo: Merge back population study importing (see implementation in the
    #     old-population-study branch).
    if filetype != 'vcf':
        raise ReadError('Data must be in VCF format')

    reader = vcf.Reader(observations)

    for record in reader:
        # Todo: Check if it is in settings.CHROMOSOMES, but support
        #     defaultdict (allowing any chromosome).
        chrom = normalize_chromosome(record.CHROM)

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
        yield chromosome, begin, end


@celery.task
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

    if variation.task_uuid is not None:
        # Todo: Check somehow if the importing task is still running.
        # http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists
        raise TaskError('variation_importing', 'Variation is being imported')

    try:
        data = variation.data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    def delete_observations():
        variation.observations.delete()

    # Note: Since we are dealing with huge numbers of entries here, we commit
    # after each INSERT and manually rollback. Using builtin session rollback
    # would fill up all our memory.
    with data as observations, database_task(cleanup=delete_observations):
        try:
            for chromosome, begin, end, reference, variant_seq, total_coverage, variant_coverage in read_observations(observations, filetype=variation.data_source.filetype):
                try:
                    variant = Variant.query.filter_by(chromosome=chromosome, begin=begin, end=end, reference=reference, variant=variant_seq).one()
                except NoResultFound:
                    variant = Variant(chromosome, begin, end, reference, variant_seq)
                    db.session.add(variant)
                    db.session.commit()
                observation = Observation(variant, variation, total_coverage=total_coverage, variant_coverage=variant_coverage)
                db.session.add(observation)
                db.session.commit()
        except ReadError as e:
            raise TaskError('invalid_observations', str(e))
        variation.imported = True

    logger.info('Finished task: import_variation(%d)', variation_id)


@celery.task
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

    if coverage.task_uuid is not None:
        # Todo: Check somehow if the importing task is still running.
        # http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists
        raise TaskError('coverage_importing', 'Coverage is being imported')

    try:
        data = coverage.data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    def delete_regions():
        coverage.regions.delete()

    # Note: Since we are dealing with huge numbers of entries here, we commit
    # after each INSERT and manually rollback. Using builtin session rollback
    # would fill up all our memory.
    with data as regions, database_task(cleanup=delete_regions):
        try:
            for chromosome, begin, end in read_regions(regions, filetype=coverage.data_source.filetype):
                db.session.add(Region(coverage, chromosome, begin, end))
                db.session.commit()
        except ReadError as e:
            raise TaskError('invalid_regions', str(e))
        coverage.imported = True

    logger.info('Finished task: import_coverage(%d)', coverage_id)


@celery.task
def annotate_vcf(data_source_id, ignore_sample_ids=None):
    """
    Annotate variants in VCF file.
    """
    logger.info('Started task: annotate_vcf(%d)', data_source_id)

    ignore_sample_ids = ignore_sample_ids or []

    data_source = DataSource.query.get(data_source_id)
    if not data_source:
        raise TaskError('data_source_not_found', 'Data source not found')

    try:
        vcf = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    annotation = Annotation(data_source)
    annotation_data = annotation.data_writer()

    # Todo: Use context manager that deletes annotation file on error.
    # Todo: In these kind of situations, maybe we also need to make sure that
    #    the Annotation instance is deleted?
    with vcf as vcf, annotation_data as annotation_data:
        # Todo: Create some sort of abstracted variant reader from the vcf
        #     file and pass that to annotate_variants.
        _write_annotation(vcf, annotation_data, ignore_sample_ids)

    db.session.add(annotation)
    db.session.commit()

    logger.info('Finished task: annotate_vcf(%d)', data_source_id)
    return annotation.id


@celery.task
def ping():
    """
    Ping-pong task usefull for testing purposes.
    """
    logger.info('Started task: ping')
    logger.info('Finished task: ping')
    return 'pong'
