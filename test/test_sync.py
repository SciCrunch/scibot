import unittest
from time import sleep
from threading import Thread
from curio import run
from scibot.sync import manager, client, Locker, done
from scibot.utils import makeSimpleLogger

log = makeSimpleLogger('sync test log')
host = 'localhost'
port = 11111
syncword = 'syncword!'


def manager_main():
    run(manager, (host, port), syncword)


def client_main(uri='aaaaaaaaaaaaaaaaaaaaaaaaaa'):
    send = run(client, (host, port), syncword)
    URL_LOCK = Locker(send)
    while not done.is_set():
        URL_LOCK.start_uri(uri)
        sleep(0.5)
        URL_LOCK.stop_uri(uri)
        sleep(1)


def main():
    manager_thread = Thread(target=manager_main, args=tuple())
    manager_thread.start()
    n_clients = 7
    messages = [chr(x + 97) * 10 for x in range(n_clients)]
    cthreads = []
    for i, msg in enumerate(messages):
        sleep(0.25)
        client_thread = Thread(target=client_main, args=(msg,))
        cthreads.append(client_thread)
        client_thread.start()

    sleep(4)
    done.set()
    log.info('waiting on clients')
    for i, t in enumerate(cthreads):
        t.join()
        log.info(f'joined client thread {i}')

    log.info('waiting on manager')  # this doesn't work
    manager_thread.join()


class TestSync(unittest.TestCase):
    def test_all(self):
        main()
