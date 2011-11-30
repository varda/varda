"""
Celery tasks.
"""


import os
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError

from varda import app, db, celery
from varda.models import Variant, Sample, Observation, DataSource


class TaskError(Exception):
    """
    Exception thrown on failed task execution.
    """
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(Exception, self).__init__(code, message)

    def to_dict(self):
        return {'code':    self.code,
                'message': self.message}


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


@celery.task
def import_bed(sample_id, data_source_id):
    """
    Import regions from BED file.
    """
    data_source = DataSource.query.get(data_source_id)
    if not data_source:
        raise TaskError('data_source_not_found', 'Data source not found')

    sample = Sample.query.get(sample_id)
    if not sample:
        raise TaskError('sample_not_found', 'Sample not found')

    # Todo: SQLAlchemy probably has something for this, has() or any() or exists()...
    if sample.regions.filter_by(data_source=data_source).count() > 1:
        raise TaskError('data_source_imported', 'Data source already imported in this sample')

    bed_file = os.path.join(app.config['FILES_DIR'], data_source.filename)

    # Note: Since we are dealing with huge numbers of entries here, we
    # commit after each INSERT and manually rollback. Using builtin
    # session rollback would fill up all our memory.
    def delete_regions():
        sample.regions.filter_by(data_source=data_source).delete()

    # Todo: This (multiple context managers) is a Python 2.7 feature
    with task_context(cleanup=delete_regions) as _, open(bed_file) as bed:

        for line in bed:
            fields = line.split()
            if len(parts) < 1 or parts[0] == 'track':
                continue
            try:
                chromosome = parts[0]
                begin = int(parts[1])
                end = int(parts[2])
            except (IndexError, ValueError):
                raise TaskError('data_source_invalid', 'Invalid line in BED file: "%s"' % line)
            region = Region(sample, data_source, chromosome, begin, end)
            db.session.add(region)
            db.session.commit()


@celery.task
def import_vcf(sample_id, data_source_id, use_genotypes=True):
    """
    Import observed variants from VCF file.

    @todo: This only works for merged population studies at the moment.
    @todo: Use custom state to report progress:
        http://docs.celeryproject.org/en/latest/userguide/tasks.html#custom-states
    """
    data_source = DataSource.query.get(data_source_id)
    if not data_source:
        raise TaskError('data_source_not_found', 'Data source not found')

    sample = Sample.query.get(sample_id)
    if not sample:
        raise TaskError('sample_not_found', 'Sample not found')

    # Todo: SQLAlchemy probably has something for this, has() or any() or exists()...
    if sample.observations.filter_by(data_source=data_source).count() > 1:
        raise TaskError('data_source_imported', 'Data source already imported in this sample')

    vcf_file = os.path.join(app.config['FILES_DIR'], data_source.filename)

    # Note: Since we are dealing with huge numbers of entries here, we
    # commit after each INSERT and manually rollback. Using builtin
    # session rollback would fill up all our memory.
    def delete_observations():
        sample.observations.filter_by(data_source=data_source).delete()

    # Todo: This (multiple context managers) is a Python 2.7 feature
    with task_context(cleanup=delete_observations), open(vcf_file) as vcf:

        header = vcf.readline()
        if 'fileformat=VCFv4.1' not in header:
            raise TaskError('data_source_invalid', 'Data source not in VCF version 4.1 format')

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
                    raise TaskError('data_source_invalid', 'Cannot read variant support')
                try:
                    observation = Observation(sample, variant, data_source, support=support)
                except IntegrityError:
                    # This should never happen since we check this above.
                    raise TaskError('data_source_imported', 'Observation already exists')
                db.session.add(observation)
                db.session.commit()
