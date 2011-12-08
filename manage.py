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
    createuser --pwprompt --encrypted --no-adduser --no-createdb --no-createrole varda
    createdb --encoding=UNICODE --owner=varda varda
    createdb --encoding=UNICODE --owner=varda vardacelery
    createdb --encoding=UNICODE --owner=varda vardaresults

Or use RabbitMQ as message broker:

    sudo rabbitmqctl add_user varda varda
    sudo rabbitmqctl add_vhost varda
    sudo rabbitmqctl set_permissions -p varda varda '.*' '.*' '.*'

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
    pietje = User('Pietje Puk', 'pietje', 'pi3tje', roles=['admin'])
    karel = User('Karel Koek', 'karel', 'k4rel', roles=['importer'])
    db.session.add(pietje)
    db.session.add(karel)
    db.session.commit()


if __name__ == '__main__':
    manager.run()
