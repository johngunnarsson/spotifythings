# -*- coding: utf-8 -*-
import tornado.ioloop
from threading import Thread

class AsyncIOLoop(Thread):

    def run(self):
        tornado.ioloop.IOLoop.instance().start()

    def stop(self):
        ioloop = tornado.ioloop.IOLoop.instance()
        ioloop.add_callback(lambda x: x.stop(), ioloop)
        self.join()

