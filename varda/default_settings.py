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

# Note: To allow any chromosome name you can use a defaultdict here.
# Number of chromosome copies in male and female (this is hg19)
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
    'X': (2, 1),
    'Y': (0, 1),
    'M': (1, 1),
    '1_gl000191_random': (2, 2),
    '1_gl000192_random': (2, 2),
    '4_ctg9_hap1': (2, 2),
    '4_gl000193_random': (2, 2),
    '4_gl000194_random': (2, 2),
    '6_apd_hap1': (2, 2),
    '6_cox_hap2': (2, 2),
    '6_dbb_hap3': (2, 2),
    '6_mann_hap4': (2, 2),
    '6_mcf_hap5': (2, 2),
    '6_qbl_hap6': (2, 2),
    '6_ssto_hap7': (2, 2),
    '7_gl000195_random': (2, 2),
    '8_gl000196_random': (2, 2),
    '8_gl000197_random': (2, 2),
    '9_gl000198_random': (2, 2),
    '9_gl000199_random': (2, 2),
    '9_gl000200_random': (2, 2),
    '9_gl000201_random': (2, 2),
    '11_gl000202_random': (2, 2),
    '17_ctg5_hap1': (2, 2),
    '17_gl000203_random': (2, 2),
    '17_gl000204_random': (2, 2),
    '17_gl000205_random': (2, 2),
    '17_gl000206_random': (2, 2),
    '18_gl000207_random': (2, 2),
    '19_gl000208_random': (2, 2),
    '19_gl000209_random': (2, 2),
    '21_gl000210_random': (2, 2),
    'Un_gl000211': (2, 2),
    'Un_gl000212': (2, 2),
    'Un_gl000213': (2, 2),
    'Un_gl000214': (2, 2),
    'Un_gl000215': (2, 2),
    'Un_gl000216': (2, 2),
    'Un_gl000217': (2, 2),
    'Un_gl000218': (2, 2),
    'Un_gl000219': (2, 2),
    'Un_gl000220': (2, 2),
    'Un_gl000221': (2, 2),
    'Un_gl000222': (2, 2),
    'Un_gl000223': (2, 2),
    'Un_gl000224': (2, 2),
    'Un_gl000225': (2, 2),
    'Un_gl000226': (2, 2),
    'Un_gl000227': (2, 2),
    'Un_gl000228': (2, 2),
    'Un_gl000229': (2, 2),
    'Un_gl000230': (2, 2),
    'Un_gl000231': (2, 2),
    'Un_gl000232': (2, 2),
    'Un_gl000233': (2, 2),
    'Un_gl000234': (2, 2),
    'Un_gl000235': (2, 2),
    'Un_gl000236': (2, 2),
    'Un_gl000237': (2, 2),
    'Un_gl000238': (2, 2),
    'Un_gl000239': (2, 2),
    'Un_gl000240': (2, 2),
    'Un_gl000241': (2, 2),
    'Un_gl000242': (2, 2),
    'Un_gl000243': (2, 2),
    'Un_gl000244': (2, 2),
    'Un_gl000245': (2, 2),
    'Un_gl000246': (2, 2),
    'Un_gl000247': (2, 2),
    'Un_gl000248': (2, 2),
    'Un_gl000249': (2, 2)
}
