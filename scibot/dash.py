from gevent import monkey
monkey.patch_all()

from scibot.dashboard import setup
app = setup()
