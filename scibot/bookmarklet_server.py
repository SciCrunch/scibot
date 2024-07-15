import os

os.sys.stdout.write(f'\x1b]2;{os.path.basename(__name__)}\x07\n')

from scibot.bookmarklet import main
app = main()

if __name__ == '__main__':
    from scibot import config
    app.run(host='localhost', port=config.port_bookmarklet, threaded=True)
