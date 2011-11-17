#!/usr/bin/env python
"""
Run the Varda REST server.

To reset the database:

    from varda import db
    db.drop_all()
    db.create_all()

"""


from flaskext.script import Manager
from flaskext.celery import install_commands as install_celery_commands

from varda import app, db


manager = Manager(app)
install_celery_commands(manager)


@manager.command
def createdb():
    """
    Create the SQLAlchemy database.
    """
    db.drop_all()
    db.create_all()


if __name__ == '__main__':
    manager.run()
