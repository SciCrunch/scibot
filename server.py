from rrid import main
from gevent.queue import Queue
from gevent.lock import RLock

URL_LOCK = RLock()
URLS = Queue()
app = main(lock=URL_LOCK, urls=URLS)
