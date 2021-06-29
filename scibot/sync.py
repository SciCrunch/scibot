#!/usr/bin/env python3
"""Run the scibot sync service

Usage:
    scibot-sync [options]

Options:
    -p --port=PORT       the port that the service should run on [default: 12345]
"""

from curio import run, socket, UniversalEvent, TaskGroup
from curio.time import timeout_after, sleep
from curio.errors import TaskTimeout, TaskCancelled
from curio.channel import Channel, Connection, AuthenticationError
from scibot.utils import log as _log

log = _log.getChild('aChannel')
slog = _log.getChild('sync')
clog = slog.getChild('client')  # TODO add process info here
mlog = slog.getChild('manager')

done = UniversalEvent()


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


class Locker:
    def __init__(self, send):
        self.send = send

    def _getQ(self):
        asdf = set()
        while 1:
            try:
                asdf.add(self.urls.get_nowait())
                print('oh boy')
            except Empty:
                break
        print('current queue', asdf)
        #print(id(self))
        return asdf

    def _setQ(self, uris):
        for uri in uris:
            log.info('putting uri', uri)
            self.urls.put(uri)
        print('done putting', uris, 'in queue')

    def start_uri(self, uri):
        val = run(self.send, 'add ' + uri)
        if val:
            return True
        else:
            return

        print(self.lock, id(self.urls))
        with self.lock:
            print(self.lock, id(self.urls))
            uris = self._getQ()
            if uri in uris:
                log.info(uri, 'is already running')
                return True
            else:
                log.info('starting work for', uri)
                uris.add(uri)
            self._setQ(uris)

    def stop_uri(self, uri):
        run(self.send, 'del ' + uri)
        return
        #print(self.lock, id(self.urls))
        with self.lock:
            #print(self.lock, id(self.urls))
            uris = self._getQ()
            uris.discard(uri)
            print('completed work for', uri)
            self._setQ(uris)


async def exit(task_group):
    await done.wait()
    clog.info(f'sync {task_group} exiting ...')  # have to call this before cancel
    await task_group.cancel_remaining()


async def manage_single_connection(connection, currently_running_urls):
    while True:
        try:
            msg = await connection.recv()
        except (EOFError, ConnectionResetError) as e:  # in the event that the client closes
            mlog.info(f'connection {connection} closed due to {e}')
            break
        else:
            op, uri = msg.split(' ', 1)
            mlog.debug(f'{op} :: {uri}')
            if op == 'add':
                if uri in currently_running_urls:
                    await connection.send(True)
                else:
                    currently_running_urls.add(uri)
                    await connection.send(False)
            elif op == 'del':
                currently_running_urls.discard(uri)
                await connection.send(False)
            else:
                await connection.send('ERROR')
        mlog.debug(currently_running_urls)


async def manager(chan, syncword):
    encoded = syncword.encode()
    currently_running_urls = set()
    async def listen_for_new_conns(task_group):
        while True:
            ch = Channel(chan)
            try:
                connection = await ch.accept(authkey=encoded)
                mlog.info(f'new connection created {connection}')
                await task_group.spawn(manage_single_connection,
                                       connection,
                                       currently_running_urls)
                await ch.close()  # sort of strange that we need this? can we connect again later !?
            except ConnectionResetError as e:
                mlog.warning('client connection attempt did not terminate property')

    async with TaskGroup() as connection_tasks:
        await connection_tasks.spawn(exit, connection_tasks)
        await connection_tasks.spawn(listen_for_new_conns, connection_tasks)


# synchronization setup
async def client(chan, syncword):
    encoded = syncword.encode()
    async def auth():
        ch = Channel(chan)
        async def connect(_ch=ch, authkey=encoded):
            connection = await _ch.connect(authkey=encoded)
            clog.debug(f'got connection {connection}')
            return connection

        async with TaskGroup(wait=any) as auth_or_exit:
            clog.info('waiting for sync services to start')
            exit_task = await auth_or_exit.spawn(exit, auth_or_exit)
            conn_task = await auth_or_exit.spawn(connect)

        connection = conn_task.result
        clog.debug(str(connection))
        return connection

    clog.info('starting auth')
    heh = [await auth()]
    async def send(uri):
        c = heh[0]
        async def sendit():
            await c.send(uri)
            resp = await c.recv()
            _uri = uri.split(' ', 1)[-1]
            msg = f'not :: {_uri}' if resp else f'run :: {_uri}'
            clog.debug(msg)
            return resp

        try:
            async with TaskGroup(wait=any) as send_or_exit:
                exit_task = await send_or_exit.spawn(exit, send_or_exit)
                send_task = await send_or_exit.spawn(sendit)

            try:
                resp = send_task.result
                return resp
            except TaskCancelled:
                return
            except RuntimeError as e:  # FIXME not quite right?
                clog.error(e)  # not eure what is causing this ... maybe a connection error?

        except (EOFError, BrokenPipeError) as e:
            c = await auth()
            heh[0] = c
            return await send(uri)

    return send


def main():
    from scibot.config import syncword
    if syncword is None:
        raise KeyError('Please set the SCIBOT_SYNC environment variable')

    import os
    try:
        # This is in a try block because colorama (used by colorlog) wraps
        # redirected stdout to strip certain control codes which can cause an
        # AttributeError: 'NoneType' object has no attribute 'set_title'
        # because colorama changes os.sys.stdout.write in a way that
        # removes the call to set_title
        os.sys.stdout.write(f'\x1b]2;{os.path.basename(__file__)}\x07\n')
    except AttributeError as e:
        slog.exception(e)

    from docopt import docopt
    args = docopt(__doc__)

    chan = ('localhost', int(args['--port']))
    run(manager, chan, syncword)


if __name__ == '__main__':
    main()
