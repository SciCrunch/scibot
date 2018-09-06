#!/usr/bin/env python3
"""Run the scibot sync service

Usage:
    scibot-sync [options]

Options:
    -p --port=PORT       the port that the service should run on [default: 12345]
"""

from curio import Channel, run
from scibot.core import syncword

if syncword is None:
    raise KeyError('Please set the RRIDBOT_SYNC environment variable')

async def consumer(chan):
    ch = Channel(chan)
    c = await ch.accept(authkey=syncword.encode())
    myset = set()
    while True:
        try:
            msg = await c.recv()
        except (EOFError, ConnectionResetError) as e:  # in the event that the client closes
            print('resetting')
            myset = set()
            c = await ch.accept(authkey=syncword.encode())
            continue
        if msg is None:  # explicit reset
            myset = set()
        else:
            op, uri = msg.split(' ', 1)
            print(op, uri)
            if op == 'add':
                if uri in myset:
                    await c.send(True)
                else:
                    myset.add(uri)
                    await c.send(False)
            elif op == 'del':
                myset.discard(uri)
                await c.send(False)
            else:
                await c.send('ERROR')
        print(myset)

def main():
    import os
    os.sys.stdout.write(f'\x1b]2;{os.path.basename(__file__)}\x07\n')
    from docopt import docopt
    args = docopt(__doc__)
    chan = ('localhost', int(args['--port']))
    run(consumer, chan)

if __name__ == '__main__':
    main()

