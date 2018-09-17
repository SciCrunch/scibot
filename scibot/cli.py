#!/usr/bin/env python3.6
"""SciBot command line utilities

Usage:
    scibot db-init    [options] [<database>]
    scibot api-sync   [options] [<database>]
    scibot ws-sync    [options] [<database>]
    scibot debug      [options] [<database>]

Options:
    -h --help       show this
    -d --debug      enable echo and embed
"""

import os
from IPython import embed


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

    elif args['api-sync']:
        session = getSession(echo=args['--debug'])
        AnnoSync = AnnoSyncFactory(session)
        cur_sync = AnnoSync(config.api_token, config.username,
                            config.group, config.memfile)
        cur_sync.sync_annos()
        pub_sync = AnnoSync(config.api_token, config.username,
                            config.group_staging, config.pmemfile)
        pub_sync.sync_annos()

    elif args['ws-sync']:
        'TODO'

    elif args['debug']:
        session = getSession(echo=args['--debug'])
        if True:
            dcount = {r.uri:r.document_id
                    for r in session.execute('SELECT uri, document_id FROM document_uri')}
            from hyputils.hypothesis import Memoizer
            from scibot.anno import disambiguate_uris
            mem = Memoizer(config.memfile, config.api_token, config.username, config.group)
            annos, last_updated = mem.get_annos_from_file()
            uris = set(a.uri for a in annos)
            dd = disambiguate_uris(uris)
            multi = [v for v in dd.values() if len(v) > 1]
            rows = [a._row for a in annos]
            AnnoSync = AnnoSyncFactory(session)
            cur_sync = AnnoSync(config.api_token, config.username, config.group)
            docs = list(cur_sync.h_create_documents(rows[:100]))
            embed()


if __name__ == '__main__':
    main()
