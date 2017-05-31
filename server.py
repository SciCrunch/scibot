from gevent import monkey
monkey.patch_all()

from rrid import main
app = main()
