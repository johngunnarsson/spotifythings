# -*- coding: utf-8 -*-
import threading
import logging
from event import EventHook

logger = logging.getLogger(__name__)

class WebSocketRegistry(object):

    def __init__(self):
        self.wsregistry = dict()
        self.wsregistry_lock = threading.Lock()
        self.on_new_client = EventHook()

    def register_ws(self, wstype, ws):
        self.wsregistry_lock.acquire()
        try:
            socketlist = self.wsregistry.get(wstype)
            if not socketlist:
                socketlist = []
                self.wsregistry[wstype] = socketlist

            socketlist.append(ws)

            self.on_new_client.fire(wstype, ws)

        finally:
            self.wsregistry_lock.release()


    def unregister_ws(self, wstype, ws):
        self.wsregistry_lock.acquire()
        try:
            socketlist = self.wsregistry[wstype]
            socketlist.remove(ws)
        finally:
            self.wsregistry_lock.release()

    def broadcast(self, wstype, msg):
        send_count = 0;

        self.wsregistry_lock.acquire()
        try:
            erroneous_sockets = []

            socketlist = self.wsregistry.get(wstype)
            if socketlist:
                for socket in socketlist:
                    try:
                        socket.write_message(msg)
                        send_count += 1

                    except Exception as e:
                        logger.exception('Error detected when sending to websocket of type %s: %s', wstype, str(e))
                        erroneous_sockets.append(socket)


                for erroneous_socket in erroneous_sockets:
                    socketlist.remove(erroneous_socket)

        finally:
            self.wsregistry_lock.release()

        return send_count > 0