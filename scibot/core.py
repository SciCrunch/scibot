import hashlib
from os import environ

api_token = environ.get('SCIBOT_API_TOKEN', 'TOKEN')  # Hypothesis API token
username = environ.get('SCIBOT_USERNAME', 'USERNAME') # Hypothesis username
group = environ.get('SCIBOT_GROUP', '__world__')
group2 = environ.get('SCIBOT_GROUP2', '__world__')
group_staging = environ.get('SCIBOT_GROUP_STAGING', '__world__')
syncword = environ.get('SCIBOT_SYNC')

if syncword is None:
    raise KeyError('Please set the SCIBOT_SYNC environment variable')

READ_ONLY = True
if group_staging == '__world__' and not READ_ONLY:
    raise IOError('WARNING YOU ARE DOING THIS FOR REAL PLEASE COMMENT OUT THIS LINE')

m = hashlib.sha256()
m.update(group.encode())
group_hash = m.hexdigest()
memfile = f'/tmp/annos-{group_hash}.pickle'

if group_hash.startswith('f'):
    print('Real annos')
elif group_hash.startswith('9'):
    print('Test annos')

m = hashlib.sha256()
m.update(group_staging.encode())
group_staging_hash = m.hexdigest()

if group_staging == '__world__':
    pmemfile = '/tmp/scibot-public-annos.pickle'
else:
    pmemfile = f'/tmp/annos-{group_staging_hash}.pickle'
