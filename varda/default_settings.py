# -*- coding: utf-8 -*-
# You can overwrite these settings in the file specified by the VARDA_SETTINGS
# environment variable.

# URL prefix to serve the Varda server API under
API_URL_PREFIX = None

# Path to serve the Aulë application from
AULE_LOCAL_PATH = None

# URL prefix to serve Aulë under
AULE_URL_PREFIX = '/aule'

# Directory to store files (uploaded and generated)
import tempfile
DATA_DIR = tempfile.mkdtemp()

# Maximum size for uploaded files
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1 gigabyte

# Secondary directory to use files from, for example uploaded there by other
# means such as SFTP (Varda will never write there, only symlink to it)
SECONDARY_DATA_DIR = None

# Have a subdirectory per user in SECONDARY_DATA_DIR (same as user login)
SECONDARY_DATA_BY_USER = False

# Location of reference genome Fasta file
GENOME = None

# Abort entire task if a reference mismatch occurs
REFERENCE_MISMATCH_ABORT = True

# Location of Celery log file
#CELERYD_LOG_FILE = '/tmp/varda-celeryd.log'

# Todo: Look into this configuration option
#CELERYD_HIJACK_ROOT_LOGGER = False

# Variant database
SQLALCHEMY_DATABASE_URI = 'sqlite://'
#SQLALCHEMY_DATABASE_URI = 'mysql://user:password@localhost/varda'
#SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/varda'

# Celery broker
BROKER_URL = 'memory://'
#BROKER_URL = 'redis://'
#BROKER_TRANSPORT = 'sqlalchemy'
#BROKER_HOST = 'mysql://user:password@localhost/vardacelery'
#BROKER_HOST = 'postgresql://user:password@localhost/vardacelery'
#BROKER_URL = 'amqp://user:password@localhost:5672/varda'

# Celery results
CELERY_RESULT_BACKEND = 'cache'
CELERY_CACHE_BACKEND = 'memory'
#CELERY_RESULT_BACKEND = 'redis://'
#CELERY_RESULT_BACKEND = 'database'
#CELERY_RESULT_DBURI = 'mysql://user:password@localhost/vardaresults'
#CELERY_RESULT_DBURI = 'postgresql://user:password@localhost/vardaresults'

# We are running the unit tests
TESTING = False
