.. _install:

Installation
============

Varda depends on a database server, a message broker, a task result backend,
`Python`_ 2.7, and several Python packages. This section walks you through
installing Varda using `PostgreSQL`_ as database server and `Redis`_ as
message broker and task result backend, which is the recommended setup.

.. note:: All operating system specific instructions assume installation on a
   `Debian`_ 7 *wheezy* system. You'll have to figure out the necessary
   adjustements yourself if you're on another system.

The following steps will get Varda running on your system with the recommended
setup:

* :ref:`install-postgresql`
* :ref:`install-redis`
* :ref:`install-virtualenv`
* :ref:`install-setup`

At the bottom of this page some :ref:`alternative setups
<install-alternatives>` are documented.


.. highlight:: bash


.. _install-quick:

If you're in a hurry
--------------------

The impatient can install and run Varda without a database server and more
such nonsense with the following steps::

    $ pip install -r requirements.txt
    $ python -m varda.commands debugserver --setup

Don't use this for anything serious though.


.. _install-postgresql:

Database server: PostgreSQL
---------------------------

Install `PostgreSQL`_ and add a user for Varda. Create a database
(e.g. ``varda``) owned by the new user. For example::

    $ sudo apt-get install postgresql
    $ sudo -u postgres createuser --superuser $USER
    $ createuser --pwprompt --encrypted --no-adduser --no-createdb --no-createrole varda
    $ createdb --encoding=UNICODE --owner=varda varda

Also install some development libraries needed for building the ``psycopg2``
Python package later::

    $ sudo apt-get install python-dev libpq-dev

.. seealso::

   :ref:`install-mysql`
     Alternatively, MySQL can be used as database server.

   :ref:`install-sqlite`
     Alternatively, SQLite can be used as database server.

   `Dialects -- SQLAlchemy documentation <http://docs.sqlalchemy.org/en/latest/dialects/index.html>`_
     In theory, any database supported by SQLAlchemy could work.


.. _install-redis:

Message broker and task result backend: Redis
---------------------------------------------

Varda uses `Celery`_ for distributing long-running tasks. A message broker is
needed for communication between the server process and worker
processes. Simply install `Redis`_ and you're done. ::

    $ sudo apt-get install redis-server

.. seealso::

   :ref:`install-rabbitmq`
     Alternatively, RabbitMQ can be used as message broker.

   `Brokers -- Celery documentation <http://docs.celeryproject.org/en/latest/getting-started/brokers/index.html>`_
     It should be possible to use any message broker and any `task result
     backend
     <http://docs.celeryproject.org/en/latest/configuration.html#task-result-backend-settings>`_
     supported by Celery.


.. _install-virtualenv:

Python virtual environment
--------------------------

It is recommended to run Varda from a Python virtual environment, using
`virtualenv`_. Installing virtualenv and creating virtual environment is not
covered here.

Assuming you created and activated a virtual environment for Varda, install
all required Python packages::

    $ pip install -r requirements.txt

Now might be a good idea to run the unit tests::

    $ nosetests -v

If everything's okay, install Varda::

    $ python setup.py install

.. seealso::

   `virtualenv`_
     ``virtualenv`` is a tool to create isolated Python environments.

   `virtualenvwrapper`_
     ``virtualenvwrapper`` is a set of extensions to the ``virtualenv``
     tool. The extensions include wrappers for creating and deleting virtual
     environments and otherwise managing your development workflow.


.. _install-setup:

Varda setup
-----------

Varda looks for its configuration in the file specified by the
``VARDA_SETTINGS`` environment variable. First create the file with your
configuration settings, for example::

    $ export VARDA_SETTINGS=~/varda/settings.py
    $ cat > $VARDA_SETTINGS
    DATA_DIR = '/data/varda'
    SQLALCHEMY_DATABASE_URI = 'postgresql://varda:*****@localhost/varda'
    BROKER_URL = 'redis://'
    CELERY_RESULT_BACKEND = 'redis://'

Make sure ``DATA_DIR`` refers to a directory that is writable for Varda. This
is where Varda stores uploaded and generated files.

A script is included to setup the database tables and add an administrator
user::

    $ varda setup

You can now proceed to :ref:`run`.

.. seealso::

   :ref:`config`
     For more information on the available configuration settings.


.. _install-alternatives:

Alternative setups
------------------

The remainder of this page documents some alternatives to the recommended
setup documented above.


.. _install-mysql:

Database server: MySQL
^^^^^^^^^^^^^^^^^^^^^^

Install `MySQL`_ and create a database (e.g. ``varda``) with all privileges
for the Varda user. For example::

    $ sudo apt-get install mysql-server
    $ mysql -h localhost -u root -p
    > create database varda;
    > grant all privileges on varda.* to varda@localhost identified by '*****';

Also install some development libraries needed for building the
``MySQL-python`` Python package later::

    $ sudo apt-get install python-dev libmysqlclient-dev

Substitute ``MySQL-python`` for ``psycopg2`` in ``requirements.txt`` before
you use it in the :ref:`install-virtualenv` section.

.. seealso::

   :ref:`install-postgresql`
     The recommended setup uses PostgreSQL as database server.


.. _install-sqlite:

Database server: SQLite
^^^^^^^^^^^^^^^^^^^^^^^

You probably already have all you need for using `SQLite`_. You can remove the
``psycopg2`` line in ``requirements.txt`` before you use it in the
:ref:`install-virtualenv` section.

.. seealso::

   :ref:`install-postgresql`
     The recommended setup uses PostgreSQL as database server.


.. _install-rabbitmq:

Message broker: RabbitMQ
^^^^^^^^^^^^^^^^^^^^^^^^

Preferably install `RabbitMQ`_ from the APT repository `provided by RabbitMQ
<http://www.rabbitmq.com/install-debian.html>`_. Example::

    $ sudo apt-get install rabbitmq-server
    $ sudo rabbitmqctl add_user varda varda
    $ sudo rabbitmqctl add_vhost varda
    $ sudo rabbitmqctl set_permissions -p varda varda '.*' '.*' '.*'

.. seealso::

   :ref:`install-redis`
     The recommended setup uses Redis as message broker.


.. _Celery: http://celeryproject.org/
.. _Debian: http://www.debian.org/
.. _MySQL: http://www.mysql.com/
.. _PostgreSQL: http://www.postgresql.org/
.. _Python: http://python.org/
.. _RabbitMQ: http://www.rabbitmq.com/
.. _Redis: http://redis.io/
.. _SQLite: http://www.sqlite.org/
.. _virtualenv: http://www.virtualenv.org/
.. _virtualenvwrapper: http://www.doughellmann.com/docs/virtualenvwrapper/
