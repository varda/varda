#!/usr/bin/env python
"""
Run the Varda REST server.

To setup the database (MySQL):

    create database varda;
    create database vardacelery;
    create database vardaresults;
    grant all privileges on varda.* to varda@localhost identified by 'varda';
    grant all privileges on vardacelery.* to varda@localhost identified by 'varda';
    grant all privileges on vardaresults.* to varda@localhost identified by 'varda';

Or (PostgreSQL):

    sudo -u postgres createuser --superuser $USER
    createuser --pwprompt --encrypted --no-adduser --no-createdb varda
    createdb --encoding=UNICODE --owner=varda varda
    createdb --encoding=UNICODE --owner=varda vardacelery
    createdb --encoding=UNICODE --owner=varda vardaresults

To reset the database:

    from varda import db
    db.drop_all()
    db.create_all()

To start Varda server:

    ./manage.py celeryd
    ./manage.py runserver

"""


from flaskext.script import Manager
from flaskext.celery import install_commands as install_celery_commands

from varda import app, db
from varda.models import User


manager = Manager(app)
install_celery_commands(manager)


@manager.command
def createdb():
    """
    Create the SQLAlchemy database.
    """
    db.drop_all()
    db.create_all()
    pietje = User('Pietje Puk', 'pietje', 'pi3tje')
    db.session.add(pietje)
    db.session.commit()


if __name__ == '__main__':
    manager.run()
