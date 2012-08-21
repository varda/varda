"""
Celery tasks.

.. moduleauthor:: Martijn Vermaat <martijn@vermaat.name>

.. Licensed under the MIT license, see the LICENSE file.
"""


from __future__ import division

import os
import uuid
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from celery.utils.log import get_task_logger
import vcf as pyvcf
from vcf.utils import trim_common_suffix
from vcf.parser import _Info as VcfInfo, field_counts as vcf_field_counts

from varda import db, celery
from varda.models import DataUnavailable, Variant, Sample, Observation, Region, DataSource, Annotation
from varda.region_binning import all_bins


logger = get_task_logger(__name__)


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


def import_variants(vcf, sample, data_source, use_genotypes=True):
    """
    .. todo:: Instead of reading from an open VCF, read from an abstracted
        variant reader.

    .. todo:: Rename import_variants to import_observations?

    .. todo:: Merge back population study importing (see old implementation
        above renamed import_variants_population_study).
    """
    reader = pyvcf.Reader(vcf)

    for entry in reader:
        chrom = normalize_chromosome(entry.CHROM)

        # DP: Raw read depth.
        if 'DP4' not in entry.INFO:
            coverage = entry.INFO['DP']

            # AF: Allele Frequency, for each ALT allele, in the same order as
            # listed.
            if 'AF' in entry.INFO:
                if isinstance(entry.INFO['AF'], (list, tuple)):
                    # Todo: Shouldn't we use an AF entry per allele?
                    support = coverage * entry.INFO['AF'][0]
                else:
                    support = coverage * entry.INFO['AF']
            # AF1: EM estimate of the site allele frequency of the strongest
            # non-reference allele.
            elif 'AF1' in entry.INFO:
                support = coverage * entry.INFO['AF1']
            else:
                raise TaskError('data_source_invalid',
                                'Cannot read variant support')

        else:
            # DP4: Number of 1) forward ref alleles; 2) reverse ref;
            # 3) forward non-ref; 4) reverse non-ref alleles, used in variant
            # calling. Sum can be smaller than DP because low-quality bases
            # are not counted.
            coverage = sum(entry.INFO['DP4'])
            support = sum(entry.INFO['DP4'][2:])

        for index, allele in enumerate(entry.ALT):
            reference, allele = trim_common_suffix(entry.REF.upper(),
                                                   str(allele).upper())
            if 'INDEL' in entry.INFO and len(reference) >= len(allele):
                end = entry.POS + len(reference) - 1
            else:
                end = entry.POS

            try:
                variant = Variant.query.filter_by(chromosome=chrom, begin=entry.POS, end=end, reference=reference, variant=allele).one()
            except NoResultFound:
                variant = Variant(chrom, entry.POS, end, reference, allele)
                db.session.add(variant)
                db.session.commit()
            try:
                # Todo: variant_coverage calculation is not correct with
                #     multiple non-ref alleles.
                observation = Observation(sample, variant, data_source, total_coverage=coverage, variant_coverage=(support // len(entry.ALT)))
            except IntegrityError:
                # This should never happen since we check this above.
                # Todo: Is this true?
                raise TaskError('data_source_imported', 'Observation already exists')
            db.session.add(observation)
            db.session.commit()


def write_annotation(vcf, annotation, ignore_sample_ids=None):
    """
    .. todo:: Instead of reading from an open VCF, read from an abstracted
        variant reader.

    .. todo:: Merge back population study annotation (see old implementation
        above renamed write_annotation_population_study).

    .. todo:: Do a real frequency calculation and add the result to an info
        column (with appropriate name).
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
                observations.append(variant.observations.filter(~Observation.sample_id.in_(ignore_sample_ids)).count())
            except NoResultFound:
                observations.append(0)
            coverage.append(Region.query.filter(Region.chromosome == chrom,
                                                Region.begin <= entry.POS,
                                                Region.end >= end,
                                                Region.bin.in_(bins),
                                                ~Region.sample_id.in_(ignore_sample_ids)).count())

        entry.add_info('OBS', observations)
        entry.add_info('COV', coverage)
        writer.write_record(entry)


@celery.task
def import_bed(sample_id, data_source_id):
    """
    Import regions from BED file.
    """
    logger.info('Started task: import_bed(%d, %d)', sample_id, data_source_id)

    sample = Sample.query.get(sample_id)
    if not sample:
        raise TaskError('sample_not_found', 'Sample not found')

    data_source = DataSource.query.get(data_source_id)
    if not data_source:
        raise TaskError('data_source_not_found', 'Data source not found')

    # Todo: SQLAlchemy probably has something for this, has() or any() or exists()...
    if sample.regions.filter_by(data_source=data_source).count() > 1:
        raise TaskError('data_source_imported', 'Data source already imported in this sample')

    try:
        bed = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    # Note: Since we are dealing with huge numbers of entries here, we commit
    # after each INSERT and manually rollback. Using builtin session rollback
    # would fill up all our memory.
    def delete_regions():
        sample.regions.filter_by(data_source=data_source).delete()

    with bed as bed, database_task(cleanup=delete_regions):
        for line in bed:
            fields = line.split()
            if len(fields) < 1 or fields[0] == 'track':
                continue
            try:
                chromosome = normalize_chromosome(fields[0])
                begin = int(fields[1])
                end = int(fields[2])
            except (IndexError, ValueError):
                raise TaskError('data_source_invalid', 'Invalid line in BED file: "%s"' % line)
            region = Region(sample, data_source, chromosome, begin, end)
            db.session.add(region)
            db.session.commit()

    logger.info('Finished task: import_bed(%d, %d)', sample_id, data_source_id)


@celery.task
def import_vcf(sample_id, data_source_id, use_genotypes=True):
    """
    Import observed variants from VCF file.

    .. todo:: This only works for merged population studies at the moment.
    .. todo:: Use `custom state <http://docs.celeryproject.org/en/latest/userguide/tasks.html#custom-states>`_
           to report progress:
    """
    logger.info('Started task: import_vcf(%d, %d)', sample_id, data_source_id)

    sample = Sample.query.get(sample_id)
    if not sample:
        raise TaskError('sample_not_found', 'Sample not found')

    data_source = DataSource.query.get(data_source_id)
    if not data_source:
        raise TaskError('data_source_not_found', 'Data source not found')

    # Todo: SQLAlchemy probably has something for this, has() or any() or exists()...
    if sample.observations.filter_by(data_source=data_source).count() > 1:
        raise TaskError('data_source_imported', 'Data source already imported in this sample')

    try:
        vcf = data_source.data()
    except DataUnavailable as e:
        raise TaskError(e.code, e.message)

    # Note: Since we are dealing with huge numbers of entries here, we commit
    # after each INSERT and manually rollback. Using builtin session rollback
    # would fill up all our memory.
    def delete_observations():
        sample.observations.filter_by(data_source=data_source).delete()

    with vcf as vcf, database_task(cleanup=delete_observations):
        # Todo: Create some sort of abstracted variant reader from the vcf
        #     file and pass that to import_variants.
        import_variants(vcf, sample, data_source, use_genotypes)
        data_source.imported = True

    logger.info('Finished task: import_vcf(%d, %d)', sample_id, data_source_id)


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
        write_annotation(vcf, annotation_data, ignore_sample_ids)

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
