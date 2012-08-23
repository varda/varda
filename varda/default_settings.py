# You can overwrite these settings in the file specified by the VARDA_SETTINGS
# environment variable.

# Enable debugging mode
DEBUG = True

# Addresses to send errors to
ADMINS = []

# Directory to store uploaded files
FILES_DIR = '/tmp/varda'

# Maximum size for uploaded files
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1 gigabyte

# Location of server log file
SERVER_LOG_FILE = '/tmp/varda-server.log'

# Location of Celery log file
#CELERYD_LOG_FILE = '/tmp/varda-celeryd.log'

# Todo: Look into this configuration option
#CELERYD_HIJACK_ROOT_LOGGER = False

# Variant database
#SQLALCHEMY_DATABASE_URI = 'mysql://user:password@localhost/varda'
SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/varda'

# Celery results
CELERY_RESULT_BACKEND = 'database'
#CELERY_RESULT_DBURI = 'mysql://user:password@localhost/vardaresults'
CELERY_RESULT_DBURI = 'postgresql://user:password@localhost/vardaresults'

# Celery broker
#BROKER_TRANSPORT = 'sqlalchemy'
#BROKER_HOST = 'mysql://user:password@localhost/vardacelery'
#BROKER_HOST = 'postgresql://user:password@localhost/vardacelery'
#BROKER_URL = 'amqp://user:password@localhost:5672/varda'
BROKER_URL = 'redis://localhost:6379/0'

# Todo: Add known unplaced contigs.
# Note: To allow any chromosome name you can use a defaultdict here.
# Number of chromosome copies in male and female
CHROMOSOMES = {
    '1': (2, 2),
    '2': (2, 2),
    '3': (2, 2),
    '4': (2, 2),
    '5': (2, 2),
    '6': (2, 2),
    '7': (2, 2),
    '8': (2, 2),
    '9': (2, 2),
    '10': (2, 2),
    '11': (2, 2),
    '12': (2, 2),
    '13': (2, 2),
    '14': (2, 2),
    '15': (2, 2),
    '16': (2, 2),
    '17': (2, 2),
    '18': (2, 2),
    '19': (2, 2),
    '20': (2, 2),
    '21': (2, 2),
    '22': (2, 2),
    'X': (1, 2),
    'Y': (1, 2),
    'M': (1, 1)
}
