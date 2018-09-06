#!/usr/bin/env python3
""" Get the 10k most recent annotations from a group. """
import json
import hashlib
from os import environ, chmod
from datetime import date
from hyputils.hypothesis import HypothesisUtils

def main():
    TODAY = date.isoformat(date.today())

    api_token = environ.get('RRIDBOT_API_TOKEN', 'TOKEN')  # Hypothesis API token
    username = environ.get('RRIDBOT_USERNAME', 'USERNAME') # Hypothesis username
    group = environ.get('RRIDBOT_GROUP', '__world__')
    group_staging = environ.get('RRIDBOT_GROUP_STAGING', '__world__')

    m = hashlib.sha256()
    m.update(group.encode())
    group_hash = m.hexdigest()[:16]  # 16 is 2x the length of the original group...
    h = HypothesisUtils(username=username, token=api_token, group=group, max_results=10000)
    # FIXME there seems to be an additiona bug here in hyputils
    # there will be an error at the end when we overrun 10k
    recent_annos = list(h.search_all({'group': h.group}))
    fn = f'annos-{group_hash}-{TODAY}.json'
    with open(fn, 'wt') as f:
        json.dump(recent_annos, f, indent=4)
    chmod(fn, 0o600)

if __name__ == '__main__':
    main()
