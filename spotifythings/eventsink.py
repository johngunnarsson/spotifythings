# -*- coding: utf-8 -*-

# python
from threading import Lock, Event
from functools import partial

# project
from event import EventHook

class EventSinkMethod(object):

    def __init__(self):
        self.lock = Lock()
        self.event_hook = None
        self.event = None
        self.one_time_subscriptions = []

    def subscribe(self, callback):
        with self.lock:
            if not self.event_hook:
                self.event_hook = EventHook()

            self.event_hook += callback

    def unsubscribe(self, callback):
        with self.lock:
            if self.event_hook:
                self.event_hook += callback

    def subscribe_once(self, callback):
        with self.lock:
            self.one_time_subscriptions.append(callback)

    def wait(self, timeout):
        with self.lock:
            if not self.event:
                self.event = Event()
            else:
                self.event.clear()

        self.event.wait(timeout)

    def handle_call(self, *args, **kwargs):
        with self.lock:
            # check if a event_hook exist
            if self.event_hook:
                self.event_hook.fire(*args, **kwargs)

            # check if event exist
            if self.event:
                self.event.set()

            # check if any one time subcriptions exist
            if self.one_time_subscriptions:
                # loop thru all all callbacks and invoke
                for callback in self.one_time_subscriptions:
                    callback(*args, **kwargs)

                # clear list
                del self.one_time_subscriptions[:]




class EventSink(object):

    def __init__(self, initial_subscriptions = None):
        self.methods_lock = Lock()
        self.sink_methods = dict()

        if initial_subscriptions:
            for event_name, callback in initial_subscriptions.items():
                self.subscribe(event_name, callback)

    def __event_sink_handler(self, name, *args, **kwargs):
        method = self.get_sink_method(name)
        method.handle_call(*args, **kwargs)

    def __getattr__(self, name):
        return partial(self.__event_sink_handler, name)


    def get_sink_method(self, name):
        with self.methods_lock:
            method = self.sink_methods.get(name, None)
            if not method:
                method = EventSinkMethod()
                self.sink_methods[name] = method

            return method

    def subscribe(self, event_name, callback):
        self.get_sink_method(event_name).subscribe(callback)

    def unsubscribe(self, event_name, callback):
        self.get_sink_method(event_name).unsubscribe(callback)

    def subscribe_once(self, event_name, callback):
        self.get_sink_method(event_name).subscribe_once(callback)

    def wait_for(self, event_name, timeout = None):
        self.get_sink_method(event_name).wait(timeout)




