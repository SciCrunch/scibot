from gevent import monkey
monkey.patch_all()

from dashboard import setup
app = setup()
