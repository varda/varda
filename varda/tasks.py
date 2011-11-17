"""
Celery tasks.
"""


from varda import celery


@celery.task
def add_three(number):
    return number + 3
