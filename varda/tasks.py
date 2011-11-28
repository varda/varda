"""
Celery tasks.
"""


import os

from sqlalchemy.exc import IntegrityError

from varda import app, db, celery
from varda.models import Variant, Sample, Observation, DataSource


class TaskError(Exception):
    pass


@celery.task
def import_vcf(sample_id, data_source_id, use_genotypes=True):
    """
    Import observed variants from VCF file.

    @todo: This only works for merged population studies at the moment.
    @todo: Check if it has already been imported.
    @todo: Use custom state to report progress:
        http://docs.celeryproject.org/en/latest/userguide/tasks.html#custom-states

    @note: Uncommitted writes to MySQL seem to be cached in memory by SQLAlchemy
        since MySQL does not have commit/rollback functionality. The unpleasant
        side-effect is that we need tons of memory if we only commit after the
        entire VCF file is imported. So we commit after each variant.
        Unfortunately, this looses the most obvious way to do error recovery by
        doing a rollback on all variants imported thus far.
    """
    data_source = DataSource.query.get(data_source_id)
    if not data_source:
        raise TaskError('Data source not found')

    vcf_file = os.path.join(app.config['FILES_DIR'], data_source.filename)
    vcf = open(vcf_file)

    header = vcf.readline()
    if 'fileformat=VCFv4.1' not in header:
        raise TaskError('Data source not in VCF version 4.1 format')

    sample = Sample.query.get(sample_id)
    if not sample:
        raise TaskError('Sample not found')

    # Todo: SQLAlchemy probably has something for this, has() or any() or exists()...
    if sample.observations.filter(data_source=data_source).count() > 1:
        raise TaskError('Data source already imported in this sample')

    for line in vcf:
        if line.startswith('#'):
            continue
        fields = line.split()
        info = dict(field.split('=') if '=' in field else (field, None) for field in fields[7].split(';'))
        chromosome, position, _, reference, variant = fields[:5]
        if use_genotypes:
            genotypes = [genotype.split(':')[0] for genotype in fields[9:]]
        for index, allele in enumerate(variant.split(',')):
            if 'SV' in info:
                # SV deletion (in 1KG)
                # Todo: For now we ignore these, reference is likely to be
                # larger than the maximum of 200 by the database schema.
                #end = int(position) + len(reference) - 1
                #allele = ''
                continue
            elif ('SVTYPE' in info and info['SVTYPE'] == 'DEL') or \
                 ('INDEL' in info and len(reference) >= len(allele)):
                # Deletion
                end = int(position) + len(reference) - 1
            else:
                # SNP or insertion.
                end = position
            variant = Variant.query.filter_by(chromosome=chromosome, begin=position, end=end, reference=reference, variant=allele).first()
            if not variant:
                variant = Variant(chromosome, position, end, reference, allele)
                db.session.add(variant)
                db.session.commit()
            if use_genotypes:
                support = sum(1 for genotype in genotypes if str(index + 1) in genotype)
            elif 'SF' in info:
                support = len(info['SF'].split(','))
            elif 'AC' in info:
                support = int(info['AC'])
            else:
                raise TaskError('Cannot read variant support')
            try:
                observation = Observation(sample, variant, data_source, support=support)
            except IntegrityError:
                raise TaskError('Observation already exists')
            db.session.add(observation)
            db.session.commit()
    vcf.close()


# Testing tasks
@celery.task
def add_variant(chromosome, begin, end, reference, variant):
    variant = Variant(chromosome, begin, end, reference, variant)
    db.session.add(variant)
    db.session.commit()
    return variant.id
