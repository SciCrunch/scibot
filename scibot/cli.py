#!/usr/bin/env python3.6
"""SciBot command line utilities

Usage:
    scibot db-init    [<database>]
    scibot api-sync   [<database>]
    scibot ws-sync    [<database>]

Options:
    -h --help       show this
"""

import os


def main():
    from docopt import docopt
    args = docopt(__doc__)
    database = args['<database>']
    if database is not None:
        os.environ.update({'SCIBOT_DATABASE': database})

    from scibot import config
    from scibot.db import getSession, init_scibot, AnnoSyncFactory

    if args['db-init']:
        # insurace, it is passed into init direclty as well
        #os.system(f'scibot-dbsetup {config.dbPort()} {database}')
        # the above should be done manually to prevent fat fingers
        init_scibot(database)

    if args['api-sync']:
        session = getSession()
        AnnoSync = AnnoSyncFactory(session)
        cur_sync = AnnoSync(config.api_token, config.username, config.group, config.memfile)
        cur_sync.sync_annos()
        #AnnoSync(config.api_token, config.username, config.group_staging, config.pmemfile)
    if args['ws-sync']:
        'TODO'


if __name__ == '__main__':
    main()
