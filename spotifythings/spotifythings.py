# -*- coding: utf-8 -*-
import sys
import time
import logging
import os

from daemon import DaemonContext
from daemon.runner import DaemonRunner
from signal import SIGTERM

from appcontainer import AppContainer

def create_appcontainer():
    return AppContainer(dict(dbfilename=os.path.join(os.path.dirname(__file__), 'spotifythings.db'), listen_port=8888))

def is_console_app():
    return len(sys.argv) == 2 and sys.argv[1] == 'console'

def configure_logging():
    logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(name)-20s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M',
        filename=os.path.join(os.path.dirname(__file__), 'spotify_things.log'),
        filemode='a')


class App():
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/null'
        self.stderr_path = '/dev/null'
        self.pidfile_path =  '/tmp/spotify_things.pid'
        self.pidfile_timeout = 5



    def run(self):
        configure_logging()

        self.app = create_appcontainer()
        self.app.start()

        while True:
            time.sleep(1)

    def terminate(self, a, b):
        if self.app:
            self.app.stop()

        logging.shutdown()
        sys.exit()


def main():

    if is_console_app():
        # config logging
        configure_logging()

        # add console logging
        root_logger = logging.getLogger()
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(logging.Formatter('%(name)-20s: %(levelname)-8s %(message)s'))
        root_logger.addHandler(console)

        # start app
        app = create_appcontainer()
        app.start()
        logging.info('[PRESS ENTER TO DIE]')
        raw_input()
        app.stop()
    else:
        # start as deamon
        app = App()
        daemon_runner = DaemonRunner(app)
        daemon_runner.daemon_context.signal_map = {SIGTERM: app.terminate}
        daemon_runner.daemon_context.working_directory = '.'
        daemon_runner.do_action()


if __name__ == '__main__':
    main()


