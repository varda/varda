"""
Celery tasks.

Todo: Chromosomes starting with 'chr' and mitochondrial genome.
Todo: Update the import and annotation code (see SOAP-based implementation in
    the ngs-data dvd branch.

Copyright (c) 2011-2012, Leiden University Medical Center <humgen@lumc.nl>
Copyright (c) 2011-2012, Martijn Vermaat <martijn@vermaat.name>

Licensed under the MIT license, see the LICENSE file.
"""


import os
import uuid
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from celery.utils.log import get_task_logger
import vcf as pyvcf

from varda import db, celery
from varda.models import DataUnavailable, Variant, Sample, Observation, DataSource, Annotation


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
    Todo: This should be in util.py or something.
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

    Upon closing, the database session is committed and if a TaskError was
    raised, the cleanup function argument is called first.

    Todo: We might add a setup function as argument.
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
    Todo: Instead of reading from an open VCF, read from an abstracted variant
        reader.
    """
    reader = pyvcf.Reader(vcf)

    for entry in reader:
        chrom = normalize_chromosome(entry.CHROM)
        if use_genotypes:
            genotypes = [s['GT'] for s in entry.samples]
        if 'SV' in entry.INFO:
            # SV deletion (in 1KG)
            # Todo: For now we ignore these, reference is likely to be
            # larger than the maximum of 200 by the database schema.
            #end = int(position) + len(reference) - 1
            #allele = ''
            continue
        elif ('SVTYPE' in entry.INFO and entry.INFO['SVTYPE'] == 'DEL') or \
             ('INDEL' in entry.INFO and len(entry.REF) >= len(entry.ALT[0])):
            # Todo: In this condition we compare the lengths of reference and
            #     alternate allele, so we should probably do this separately
            #     for each allele (i.e. move this inside the loop below).
            # Deletion
            end = entry.POS + len(entry.REF) - 1
        else:
            # SNP or insertion.
            end = entry.POS
        for index, allele in enumerate(str(a) for a in entry.ALT):
            variant = Variant.query.filter_by(chromosome=chrom, begin=entry.POS, end=end, reference=entry.REF, variant=allele).first()
            if not variant:
                variant = Variant(chrom, entry.POS, end, entry.REF, allele)
                db.session.add(variant)
                db.session.commit()
            if use_genotypes:
                support = sum(1 for genotype in genotypes if str(index + 1) in genotype)
            elif 'SF' in entry.INFO:
                support = len(entry.INFO['SF'])  # Was: len(info['SF'].split(','))
            elif 'AC' in entry.INFO:
                support = entry.INFO['AC'][0]
            else:
                raise TaskError('data_source_invalid', 'Cannot read variant support')
            try:
                observation = Observation(sample, variant, data_source, support=support)
            except IntegrityError:
                # This should never happen since we check this above.
                raise TaskError('data_source_imported', 'Observation already exists')
            db.session.add(observation)
            db.session.commit()


def write_annotation(vcf, annotation):
    """
    Todo: Instead of reading from an open VCF, read from an abstracted variant
        reader.
    """
    reader = pyvcf.VCFReader(vcf)

    #annotation.write('## Number of samples in database: %i\n' % Sample.query.all().count())
    annotation.write('#CHROM\tPOS\tREF\tALT\tObservations\n')

    for entry in reader:
        chrom = normalize_chromosome(entry.CHROM)
        if 'SV' in entry.INFO:
            # SV deletion (in 1KG)
            # Todo: For now we ignore these, reference is likely to be
            # larger than the maximum of 200 by the database schema.
            #end = int(position) + len(reference) - 1
            #allele = ''
            continue
        elif ('SVTYPE' in entry.INFO and entry.INFO['SVTYPE'] == 'DEL') or \
             ('INDEL' in entry.INFO and len(entry.REF) >= len(entry.ALT[0])):
            # Deletion
            end = entry.POS + len(entry.REF) - 1
        else:
            # SNP or insertion.
            end = entry.POS
        for index, allele in enumerate(str(a) for a in entry.ALT):
            variant = Variant.query.filter_by(chromosome=chrom, begin=entry.POS, end=end, reference=entry.REF, variant=allele).first()
            if variant:
                observations = variant.observations.count()
            else:
                observations = 0
            annotation.write('\t'.join([chrom, str(entry.POS), entry.REF, allele, str(observations)]) + '\n')


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
            if len(parts) < 1 or parts[0] == 'track':
                continue
            try:
                chromosome = normalize_chromosome(parts[0])
                begin = int(parts[1])
                end = int(parts[2])
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

    @todo: This only works for merged population studies at the moment.
    @todo: Use custom state to report progress:
        http://docs.celeryproject.org/en/latest/userguide/tasks.html#custom-states
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

    logger.info('Finished task: import_vcf(%d, %d)', sample_id, data_source_id)


@celery.task
def annotate_vcf(data_source_id):
    """
    Annotate variants in VCF file.
    """
    logger.info('Started task: annotate_vcf(%d)', data_source_id)

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
        write_annotation(vcf, annotation_data)

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
