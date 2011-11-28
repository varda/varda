"""
Celery tasks.
"""


import os

from varda import app, db, celery
from varda.models import Variant, Sample, Observation, DataSource


@celery.task
def import_merged_vcf(sample_id, data_source_id, use_genotypes=True):
    """
    Import merged variants from VCF file.

    @todo: Make proper use of session commit.
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
    vcf_file = os.path.join(app.config['FILES_DIR'], data_source.filename)

    vcf = open(vcf_file)

    header = vcf.readline()
    if 'fileformat=VCFv4.1' not in header:
        #sys.stderr.write('Expected VCF version 4.1 format\n' % line)
        #sys.exit(1)
        return

    sample = Sample.query.get(sample_id)

    if not sample:
        #sys.stderr.write('No sample with sample id %d\n' % sample_id)
        #sys.exit(1)
        return

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
                #sys.error.write('Cannot read variant support\n')
                #sys.exit(1)
                continue
            #db.addObservation(variant_id, sample_id, pool_size, support)
            observation = Observation(sample, variant, data_source, support=support)
            db.session.add(observation)
            db.session.commit()
    db.session.commit()
    vcf.close()


# Testing tasks
@celery.task
def add_variant(chromosome, begin, end, reference, variant):
    variant = Variant(chromosome, begin, end, reference, variant)
    db.session.add(variant)
    db.session.commit()
    return variant.id
