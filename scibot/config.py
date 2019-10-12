import sys
from os import environ
from socket import gethostname
from pathlib import Path
from hyputils.hypothesis import group_to_memfile, ucd

# ports
port_bookmarklet = 4443
port_dashboard = 8080

## WARNING if you change one of these update the file in bin/
port_guni_bookmarket = 5000     # scibot-bookmarklet
port_guni_dashboard = 5005      # scibot-dashboard

# dev
dev_remote_hosts = 'athena', 'arachne'

# testing
test_host = 'localhost'
test_port = port_bookmarklet
test_database = '__scibot_testing'

# db
user = 'scibot-user'
database = environ.get('SCIBOT_DATABASE', test_database)


def dbPort():
    return 54321 if gethostname() in dev_remote_hosts else 5432


def dbUri(user=user, host='localhost', port=dbPort(), database=database):
    if hasattr(sys, 'pypy_version_info'):
        dialect = 'psycopg2cffi'
    else:
        dialect = 'psycopg2'
    return f'postgresql+{dialect}://{user}@{host}:{port}/{database}'


# mq
vhost = 'scibot'
broker_url = environ.get('CELERY_BROKER_URL',
                         environ.get('BROKER_URL',
                                     'amqp://guest:guest@localhost:5672//'))
broker_backend = environ.get('CELERY_BROKER_BACKEND',
                             environ.get('BROKER_BACKEND',
                                         'rpc://'))
accept_content = ('pickle', 'json')

# logging
source_log_location = environ.get('SOURCE_LOG_LOC',
                                  (Path(__file__).parent.parent /
                                   'logs').as_posix())

# hypothesis
api_token = environ.get('SCIBOT_API_TOKEN', 'TOKEN')  # Hypothesis API token
username = environ.get('SCIBOT_USERNAME', 'USERNAME') # Hypothesis username
group = environ.get('SCIBOT_GROUP', '__world__')
group2 = environ.get('SCIBOT_GROUP2', '__world__')
group_staging = environ.get('SCIBOT_GROUP_STAGING', '__world__')
syncword = environ.get('SCIBOT_SYNC')

READ_ONLY = True
if group_staging == '__world__' and not READ_ONLY:
    raise IOError('WARNING YOU ARE DOING THIS FOR REAL PLEASE COMMENT OUT THIS LINE')

def _post(group_hash):
    if group_hash.startswith('f'):
        print('Real annos')
    elif group_hash.startswith('9'):
        print('Test annos')

memfile = group_to_memfile(group, _post)

pmemfile =  f'{ucd}/scibot/annos-__world__-{username}.json'

if group_staging == '__world__':
    smemfile = f'{ucd}/scibot/annos-__world__-{username}.json'
else:
    smemfile = group_to_memfile(group_staging)

# rrid resolver
resolver_xml_filepath = Path('~/ni/dev/rrid/scibot/scibot_rrid_xml.pickle').expanduser()  # FIXME
