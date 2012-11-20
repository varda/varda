# You can overwrite these settings in the file specified by the VARDA_SETTINGS
# environment variable.

# Directory to store uploaded files
FILES_DIR = '/tmp'

# Maximum size for uploaded files
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1 gigabyte

# Location of reference genome Fasta file
GENOME = None

# Abort entire task if a reference mismatch occurs
REFERENCE_MISMATCH_ABORT = True

# Location of Celery log file
#CELERYD_LOG_FILE = '/tmp/varda-celeryd.log'

# Todo: Look into this configuration option
#CELERYD_HIJACK_ROOT_LOGGER = False

# Variant database
#SQLALCHEMY_DATABASE_URI = 'sqlite://'
#SQLALCHEMY_DATABASE_URI = 'mysql://user:password@localhost/varda'
SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/varda'

# Celery broker
#BROKER_TRANSPORT = 'sqlalchemy'
#BROKER_HOST = 'mysql://user:password@localhost/vardacelery'
#BROKER_HOST = 'postgresql://user:password@localhost/vardacelery'
#BROKER_URL = 'amqp://user:password@localhost:5672/varda'
BROKER_URL = 'redis://'

# Celery results
#CELERY_RESULT_BACKEND = 'database'
#CELERY_RESULT_DBURI = 'mysql://user:password@localhost/vardaresults'
#CELERY_RESULT_DBURI = 'postgresql://user:password@localhost/vardaresults'
CELERY_RESULT_BACKEND = 'redis://'
