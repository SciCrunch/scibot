#!/usr/bin/env python3
"""Run the scibot sync service

Usage:
    scibot-sync [options]

Options:
    -p --port=PORT       the port that the service should run on [default: 12345]
"""

from curio import run, socket
from curio.task import timeout_after, sleep
from curio.errors import TaskTimeout
from curio.channel import Channel, Connection, AuthenticationError
from scibot.utils import makeSimpleLogger

log = makeSimpleLogger('scibot.aChannel')
clog = makeSimpleLogger('scibot.sync')


class aChannel(Channel):
    async def connect(self, *, authkey=None, attempts=None):
        nattempts = 0
        while True:
            try:
                sock = socket.socket(self.family, socket.SOCK_STREAM)
                await sock.connect(self.address)
                sock_stream = sock.as_stream()
                c = Connection(sock_stream, sock_stream)
                #raise BaseException
                try:
                    async with timeout_after(1):
                        if authkey:
                            await c.authenticate_client(authkey)
                    return c
                except TaskTimeout:
                    log.warning('Channel connection to %s timed out', self.address)
                    await c.close()
                    del c
                    del sock_stream

            except OSError as e:
                if attempts is not None:
                    if nattempts >= attempts:
                        raise e
                    else:
                        nattempts += 1
                else:
                    log.error('Channel connection to %s failed', self.address, exc_info=True)

                await sock.close()
                await sleep(1)



async def sync_manager(chan, syncword):
    """ sync manager for a SINGLE gunicorn worker pool that can share
        access to the same upstream connection NOTE that any other
        process with the access key can rejoin after the initial
        accept the given chan (port)

        NOTE this does not currently support > 1 master process

        For the record, this is stupidly cpu inefficient.
    """

    ch = Channel(chan)
    while True:
        try:
            c = await ch.accept(authkey=syncword.encode())
            clog.info('initial connection made')
            break
        except ConnectionResetError as e:
            clog.warning('client connection attempt did not terminate property')

    myset = set()
    while True:
        try:
            msg = await c.recv()
        except (EOFError, ConnectionResetError) as e:  # in the event that the client closes
            clog.info(f'resetting due to {e}')
            myset = set()
            c = await ch.accept(authkey=syncword.encode())
            continue
        if msg is None:  # explicit reset
            myset = set()
        else:
            op, uri = msg.split(' ', 1)
            clog.debug(f'{op} -> {uri}')
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
        clog.debug(myset)

def main():
    from scibot.core import syncword
    if syncword is None:
        raise KeyError('Please set the SCIBOT_SYNC environment variable')

    import os
    os.sys.stdout.write(f'\x1b]2;{os.path.basename(__file__)}\x07\n')

    from docopt import docopt
    args = docopt(__doc__)

    chan = ('localhost', int(args['--port']))
    run(sync_manager, chan, syncword)

if __name__ == '__main__':
    main()

