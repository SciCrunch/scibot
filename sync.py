#!/usr/bin/env python3

from os import environ
from curio import Channel, run
syncword = environ.get('RRIDBOT_SYNC')
chan = ('localhost', 12345)
async def consumer():
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

if __name__ == '__main__':
    run(consumer)

