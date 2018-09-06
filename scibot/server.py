from gevent import monkey
monkey.patch_all()

from scibot.rrid import main
app = main()
