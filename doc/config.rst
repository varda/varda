.. _config:

Configuration
=============

.. highlight:: bash

This section describes how to configure Varda and includes a list of all
available configuration settings.

Varda looks for its configuration in the file specified by the
``VARDA_SETTINGS`` environment variable. Make sure to always have this
environment variable set when invoking any component of Varda. One way of
doing this is by exporting it::

    $ export VARDA_SETTINGS=~/varda/settings.py

If you like, you can add this command to your ``~/.bashrc`` to have it
executed every time you open a shell.

Another way is by prefixing your invocations with ``VARDA_SETTINGS=...``. For
example::

    $ VARDA_SETTINGS=~/varda/settings.py varda debugserver


Example configuration
---------------------

.. highlight:: python

If you followed the steps in :ref:`install`, this is a standard configuration
file that will work for you::

    DATA_DIR = '/data/varda'
    SQLALCHEMY_DATABASE_URI = 'postgresql://varda:*****@localhost/varda'
    BROKER_URL = 'redis://'
    CELERY_RESULT_BACKEND = 'redis://'

This is not yet a minimal configuration. In fact, you can run Varda without a
configuration file since the default configuration works out of the box. The
default configuration uses an in-memory database, broker, and task result
backend and a temporary directory for file storage, so it is not recommended
for anything more than playing around.

The next section describes all available configuration settings.


Configuration settings
----------------------

Note that the configuration file is interpreted as a Python module, so you can
use arbitrary Python expressions as configuration values, or even import other
modules in it.

Unsetting a configuration setting is done by using the value `None`. If no
default value is mentioned for any configuration setting below it means it is
not set by default.


HTTP server settings
^^^^^^^^^^^^^^^^^^^^

API_URL_PREFIX
  URL prefix to serve the Varda server API under.

MAX_CONTENT_LENGTH
  Maximum size for uploaded files.

  `Default value:` `1024**3` (1 gigabyte)

CORS_ALLOW_ORIGIN
  A URI (or ``*``) that may access resources via `cross-origin resource
  sharing (CORS) <>`_, used in the `Access-Control-Allow-Origin response
  header <https://developer.mozilla.org/en-US/docs/Web/HTTP/Access_control_CORS#Access-Control-Allow-Origin>`_.

  `Default value:` `None`


Data files settings
^^^^^^^^^^^^^^^^^^^

DATA_DIR
  Directory to store files (uploaded and generated).

  `Default value:` `tempfile.mkdtemp()` (a temporary directory)

SECONDARY_DATA_DIR
  Secondary directory to use files from, for example uploaded there by other
  means such as SFTP (Varda will never write there, only symlink to it).

SECONDARY_DATA_BY_USER
  Have a subdirectory per user in SECONDARY_DATA_DIR (same as user login).

  `Default value:` `False`


Reference genome settings
^^^^^^^^^^^^^^^^^^^^^^^^^

GENOME
  Location of reference genome Fasta file.

  Varda can use a reference genome to check and normalize variant
  descriptions. Specify the location to a FASTA file with the ``GENOME``
  setting in the configuration file::

      $ cat >> $VARDA_SETTINGS
      GENOME = '/usr/local/genomes/hg19.fa'
      REFERENCE_MISMATCH_ABORT = True

 A Samtools "faidx" compatible index file will automatically be created if it
 does not exist yet.

REFERENCE_MISMATCH_ABORT
  Abort entire task if a reference mismatch occurs.

  `Default value:` `True`


Database settings
^^^^^^^^^^^^^^^^^

SQLALCHEMY_DATABASE_URI
  SQLAlchemy database connection URI specifying the database used to store
  users, samples, variants, etcetera.

  ================   ============================================
  Database system    Example URI
  ================   ============================================
  PostgreSQL         ``postgresql://user:*****@localhost/varda``
  MySQL              ``mysql://user:*****@localhost/varda``
  SQLite             ``sqlite:///varda.db``
  ================   ============================================

  See the SQLAlchemy documentation on
  `Engine Configuration
  <http://docs.sqlalchemy.org/en/latest/core/engines.html>`_ for more
  information.

  `Default value:` ``sqlite://`` (in-memory SQLite database)


Celery settings
^^^^^^^^^^^^^^^

The most relevant configuration settings for varda relating to Celery are
described here, but many more are available. See the Celery documentation on
`Configuration and defaults
<http://docs.celeryproject.org/en/latest/configuration.html#example-configuration-file>`_
for information on all available configuration settings.

BROKER_URL
  Message broker connection URL used by Celery.

  ==============  ============================================
  Broker system   Example URI
  ==============  ============================================
  Redis           ``redis://``
  RabbitMQ        ``amqp://varda:*****@localhost:5672/varda``
  ==============  ============================================

  See the Celery documentation on `Broker settings
  <http://docs.celeryproject.org/en/latest/configuration.html#broker-settings>`_
  for more information.

  `Default value:` ``memory://``

CELERY_RESULT_BACKEND
  Task result backend used by Celery.

  ==========================  =============
  Backend system
  ==========================  =============
  Redis                       ``redis://``
  Database using SQLAlchemy   ``database``
  memcached                   ``cache``
  ==========================  =============

  `Default value:` ``cache``

  See the Celery documentation on `Task result backend settings
  <http://docs.celeryproject.org/en/latest/configuration.html#task-result-backend-settings>`_
  for more information.

CELERY_RESULT_DBURI
  SQLAlchemy database connection URI specifying the database used by Celery as
  task result backend if `CELERY_RESULT_BACKEND` is set to ``database``.

CELERY_CACHE_BACKEND
  memcached connection URI specifying the server(s) used by Celery as task
  result backend if `CELERY_RESULT_BACKEND` is set to ``cache``.

  `Default value:` ``memory`` (no server, stored in memory only)

CELERYD_LOG_FILE
  Location of Celery log file.

CELERYD_HIJACK_ROOT_LOGGER
  Todo: Look into this setting.


Miscellaneous settings
^^^^^^^^^^^^^^^^^^^^^^

TESTING
  If set to `True`, Varda assumes to be running its unit tests. This is done
  automatically in the provided test suite, so you should never have to change
  this setting.

  `Default value:` `False`
