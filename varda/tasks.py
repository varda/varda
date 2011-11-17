"""
Celery tasks.
"""


from varda import celery, db
from varda.models import Variant


# Testing tasks
@celery.task
def add_variant(chromosome, begin, end, reference, variant):
    variant = Variant(chromosome, begin, end, reference, variant)
    db.session.add(variant)
    db.session.commit()
    return variant.id
