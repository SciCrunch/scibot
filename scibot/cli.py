#!/usr/bin/env python3.6
"""SciBot command line utilities

Usage:
    scibot dbinit [<database>]

Options:
    -h --help       show this
"""

import os


def main():
    from docopt import docopt
    args = docopt(__doc__)

    if args['dbinit']:
        database = args['<database>']
        os.environ.update({'SCIBOT_DATABASE': database})
        # insurace, it is passed into init direclty as well
        from scibot import config
        from scibot.db import init_scibot
        #os.system(f'scibot-dbsetup {config.dbPort()} {database}')
        # the above should be done manually to prevent fat fingers
        init_scibot(database)


if __name__ == '__main__':
    main()
