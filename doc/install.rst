Installation
============

.. note:: Following this guide will give you a running Varda server suitable
    for a development environment. Deployment to a production server will
    probably deviate on some points (but shoudn't be done anyway since this
    is pre-alpha software).

.. note:: This guide assumes installation on a `Debian <http://www.debian.org>`_
    (testing, or *wheezy*) system with Python 2.7.

.. todo:: Have another look at broker and result backend choices. I gues the
    most typical Celery setup is to have rabbitmq as a broker and redis as a
    result backend. But since our tasks are not very high volume and rabbitmq
    is a bit heavier-weight than redis, the most sensible for us might be to
    just use redis for both. See also `this thread <http://stackoverflow.com/questions/9140716/whats-the-advantage-of-using-celery-with-rabbitmq-over-redis-mongodb-or-django>`_.

Getting Varda running consists of the following steps:

* `Installing a database server`_
* `Installing a message broker`_
* `Setting up a Python virtual environment`_
* `Creating initial configuration`_
* `Setting up the database`_
* `Running Varda`_


.. _database:

Installing a database server
----------------------------

The recommended database server is `PostreSQL <http://www.postgresql.org>`_,
but `MySQL <http://www.mysql.com>`_ will also work. You might even get away
with `SQLite <http://www.sqlite.org>`_. Choose one of the three.

(In theory, any database supported by `SQLAlchemy <http://www.sqlalchemy.org>`_
could work.)


Option 1: PostgreSQL
^^^^^^^^^^^^^^^^^^^^

Install PostgreSQL and add a user for Varda. Create two empty databases,
``varda`` and ``vardaresults``, both owned by the new user. For example::

    $ sudo aptitude install postgresql
    $ sudo -u postgres createuser --superuser $USER
    $ createuser --pwprompt --encrypted --no-adduser --no-createdb --no-createrole varda
    $ createdb --encoding=UNICODE --owner=varda varda
    $ createdb --encoding=UNICODE --owner=varda vardaresults

Also install some development libraries needed for building the psycopg2
Python package::

    $ sudo aptitude install python-dev libpq-dev


Option 2: MySQL
^^^^^^^^^^^^^^^

Example installation and setup of MySQL::

    $ sudo aptitude install mysql-server
    $ mysql -h localhost -u root -p
    > create database varda;
    > create database vardaresults;
    > grant all privileges on varda.* to varda@localhost identified by '*******';
    > grant all privileges on vardaresults.* to varda@localhost identified by '*******';

Install some development libraries needed for building the MySQL-python
package::

    $ sudo aptitutde install python-dev libmysqlclient-dev

Substitute ``MySQL-python`` for ``psycopg2`` in the ``requirements.txt``
before you use it in the :ref:`varda-virtualenv` section.


Option 3: SQLite
^^^^^^^^^^^^^^^^

I think you have all you need. You can remove the ``psycopg2`` line in
``requirements.txt``.


.. _broker:

Installing a message broker
---------------------------

A message broker is needed for communication between the server process and
worker processes. The recommended message broker is `Redis <http://redis.io>`_::

    $ sudo aptitude install redis-server

Alternatively, `RabbitMQ <http://www.rabbitmq.com/>`_ can be used as message
broker (prefarably add the APT repository `provided by RabbitMQ <http://www.rabbitmq.com/install-debian.html>`_).
Example::

    $ sudo aptitude install rabbitmq-server
    $ sudo rabbitmqctl add_user varda varda
    $ sudo rabbitmqctl add_vhost varda
    $ sudo rabbitmqctl set_permissions -p varda varda '.*' '.*' '.*'

The message broker is interfaced by `Celery <http://celeryproject.org>`_,
so you should be able to use any broker `supported by Celery <http://docs.celeryproject.org/en/latest/getting-started/brokers/index.html>`_.
Although not recommended, it can even be your database server.


.. _varda-virtualenv:

Setting up a Python virtual environment
---------------------------------------

It is recommended to run Varda from a Python virtual environment, using
`virtualenv <http://www.virtualenv.org/>`_. Managing virtual environments is
easiest using `virtualenvwrapper <http://www.doughellmann.com/docs/virtualenvwrapper/>`_.

Install `pip <http://www.pip-installer.org/en/latest/index.html>`_, virtualenv,
and virtualenvwrapper::

    $ sudo easy_install pip
    $ sudo pip install virtualenv
    $ sudo pip install virtualenvwrapper
    $ mkdir ~/.virtualenvs

Add the following to your ``~/.bashrc`` and start a new shell::

    export WORKON_HOME=~/.virtualenvs
    if [ -f /usr/local/bin/virtualenvwrapper.sh ]; then
        source /usr/local/bin/virtualenvwrapper.sh
    fi
    export PIP_VIRTUALENV_BASE=$WORKON_HOME
    export PIP_REQUIRE_VIRTUALENV=true
    export PIP_RESPECT_VIRTUALENV=true

Create the environment for Varda and install all required Python packages::

    $ mkvirtualenv varda
    $ pip install -r requirements.txt

Now might be a good idea to run the unit tests::

    $ nosetests -v

The remainder of this guide assumes the virtual environment is activated.


.. _configuration:

Creating initial configuration
------------------------------

Varda looks for its configuration in the file specified by the
``VARDA_SETTINGS`` environment variable. First create the file with your
configuration settings, for example::

    $ export VARDA_SETTINGS=~/varda/settings.py
    $ cat > $VARDA_SETTINGS
    FILES_DIR = '/tmp/varda'
    SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/varda'
    BROKER_URL = 'redis://'
    CELERY_RESULT_BACKEND = 'redis://'

Some example settings can be found in ``varda/default_settings.py``.

Make sure to always have the ``VARDA_SETTINGS`` environment variable set when
invoking any component of Varda. One way of doing this is adding the above
``export`` command to your ``~/.bashrc``. Another is prefixing your
invocations with ``VARDA_SETTINGS=...``.

Varda can use a reference genome to check and normalize variant descriptions.
Specify the location to a FASTA file with the ``GENOME`` setting in the
configuration file and flatten it in place::

    $ cat >> $VARDA_SETTINGS
    GENOME = '/usr/local/genomes/hg19.fa'
    REFERENCE_MISMATCH_ABORT = True
    $ pyfasta flatten hg19.fa


.. _database-setup:

Setting up the database
-----------------------

A script is included to setup the database tables and add an administrator
user::

    $ python -m varda.manage setup


.. _running:

Running Varda
-------------

Start a Celery worker node (only used for long-running tasks)::

    $ celery -A varda.worker.celery worker -l info --maxtasksperchild=4 --purge

And start a local Varda testserver in debug mode::

    $ python -m varda.manage debugserver

You can now point your webbrowser to the URL that is printed and see a json-
encoded status page.

There are many possibilities for deploying Varda server to a production
server. Recommended is the `Gunicorn WSGI HTTP Server <http://gunicorn.org/>`_,
which you could use like this::

    $ gunicorn varda:create_app\(\) -w 4 -t 600 --max-requests=1000
