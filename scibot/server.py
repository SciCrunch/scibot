from gevent import monkey
monkey.patch_all()

import os

os.sys.stdout.write(f'\x1b]2;{os.path.basename(__name__)}\x07\n')

from scibot.rrid import main
app = main()
