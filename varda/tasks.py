"""
Celery tasks.
"""


from varda import celery, db
from varda.models import Variant, Population, MergedObservation


@celery.task
def import_merged_vcf(population_id, vcf_file, use_genotypes=True):
    """
    Import merged variants from VCF file.

    @todo: make proper use of session commit.
    """
    vcf = open(vcf_file)

    header = vcf.readline()
    if 'fileformat=VCFv4.1' not in header:
        #sys.stderr.write('Expected VCF version 4.1 format\n' % line)
        #sys.exit(1)
        return

    population = Population.query.get(population_id)

    if not population:
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
            observation = MergedObservation(population, variant, support)
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
