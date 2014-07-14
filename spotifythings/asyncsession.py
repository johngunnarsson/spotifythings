#!/usr/bin/env python
# -*- coding: utf8 -*-

import Queue
import threading
import exceptions
import binascii
import logging
import time
import os

import spotify
from spotify import Settings, AlbumBrowser, Link, SpotifyError
from playqueue import PlayeQueueManager
from event import EventHook
from eventsink import EventSink
from alsaplayer import AlsaPlayer

logger = logging.getLogger(__name__)


class AsyncLoadedItem(object):

    def __init__(self, obj, is_loaded, callback):
        self.obj = obj
        self.is_loaded = is_loaded
        self.callback = callback

    def check_is_loaded(self):
        if self.is_loaded(self.obj):
            self.callback(self.obj)
            return True

        return False

class LinkPreview(object):

    def __init__(self, name, type, image_id, uri):
        self.name = name
        self.type = type
        self.image_id = image_id
        self.uri = uri


class EventThreadState(object):

    def __init__(self):
        self.timeout = 0
        self.current_command = None
        self.command_in_progress = threading.Event()

    def begin_cmd(self, cmd_name):
        self.current_command = cmd_name
        self.command_in_progress.set()

        logger.debug("Starting command: {0}".format(self.current_command))


    def end_cmd(self):
        logger.debug("Command: {0} DONE".format(self.current_command))

        self.current_command = None
        self.command_in_progress.clear()


    def is_cmd_inprogress(self):
        return self.command_in_progress.is_set()




class SpotifyEventThread(threading.Thread):

    def __init__(self, session):
        threading.Thread.__init__(self, name="async_event_loop")
        self.session = session
        self.ctrlqueue = Queue.Queue()
        self.cmdqueue = Queue.Queue()

    def run(self):
        logger.debug('Started Spotify event loop')

        running = True
        state = EventThreadState()

        def command_done():
            # no command is in progress
            state.end_cmd()

            # check if there are more command that awaits execution
            self.check_cmd()

        def do_process_events():
            state.timeout = self.session.process_events() / 1000.0
            if state.is_cmd_inprogress():
                logger.debug("Processed events, command {0} still executing".format(state.current_command))



        while running:
            try:

                try:

                    ctrl_msg = self.ctrlqueue.get(timeout=state.timeout)

                    if ctrl_msg == 'process_events':
                        do_process_events()
                    elif ctrl_msg == 'terminate':
                        logger.debug('Terminating Spotify event loop')
                        running = False
                    elif ctrl_msg == 'check_cmd' and not state.is_cmd_inprogress():
                        # try get command
                        command = self.cmdqueue.get_nowait()

                        # signal command in progress so that no new commands will be executed
                        state.begin_cmd(command.__name__)
                        try:
                            command(self.session, command_done)
                        except:
                            # when error, always make sure that command is considered done
                            command_done()
                            raise

                except Queue.Empty:
                    do_process_events()

            except exceptions.Exception as e:
                logger.exception('Error in thread: %s', repr(e))

    def check_cmd(self):
        self.ctrlqueue.put('check_cmd')

    def terminate(self):
        self.ctrlqueue.put('terminate')

    def process_events(self):
        self.ctrlqueue.put('process_events')

    def enqueue_cmd(self, command_function):
        # put command in queue
        self.cmdqueue.put(command_function)

        # notify ctrl queue that a new command has arrived
        self.check_cmd()

class SpotifyAsyncSessionException(Exception):
    pass



class SpotifyAsyncSessionManager(object):

    cache_location = 'tmp'
    settings_location = 'tmp'
    application_key = None
    appkey_file = os.path.join(os.path.dirname(__file__), 'spotify_appkey.key')



    def __init__(self, useragent, proxy=None, proxy_username=None, proxy_password=None):

        # Event thread
        self.event_thread = None

        # Session event sink
        self.session_event_sink = EventSink({
            '_manager_logged_out': self.__session_logged_out,
            'notify_main_thread': self.__session_notify_main_thread,
            'logged_in': self.__session_logged_in,
            'metadata_updated': self.__session_metadata_updated,
            'connection_error': self.__session_connection_error,
            'message_to_user': self.__session_message_to_user,
            'play_token_lost': self.__session_play_token_lost,
            'log_message': self.__session_log_message,
            'end_of_track': self.__session_end_of_track,
            'credentials_blob_updated': self.__credentials_blob_updated
        })

        # Redirect methods that do need to return a value
        self.session_event_sink.music_delivery = self.__session_music_delivery


        # Proxy settings
        self.session_event_sink.proxy = proxy
        self.session_event_sink.proxy_username = proxy_username
        self.session_event_sink.proxy_password = proxy_password

        # Session settings
        settings = Settings()
        if self.application_key is None:
            self.application_key = open(self.appkey_file).read()

        settings.application_key = self.application_key
        settings.cache_location = self.cache_location
        settings.settings_location = self.settings_location
        settings.user_agent = useragent

        # Logged in state
        self.is_logged_in = False
        self.login_error = 'Not logged in yet'

        # Create session
        self.session = spotify.Session.create(self.session_event_sink, settings)
        self.playlist_container = None

        # Queue manager
        self.play_queue_mgr = PlayeQueueManager()

        # Metadata waitinglist
        self.metadata_waiters = []

        # Play state
        self.is_playing = False
        self.current_track = None
        self.track_playback_time = 0
        self.last_track_playback_time_notified = 0

        # Audio sink
        #self.audio = AlsaSink(backend=self)
        self.audio = AlsaPlayer()
        self.audio_sink_lock = threading.Lock()

        # Event notifications
        self.current_track_changed = EventHook()
        self.playback_progress = EventHook()
        self.player_state_changed = EventHook()
        self.playqueue_changed = EventHook()
        self.login_state_changed = EventHook()
        self.password_blob_changed = EventHook()

    # Spotify session events
    # Internal events
    def __session_logged_out(self, session):
        logger.debug('Logged out')
        self.is_logged_in = False
        self.playlist_container = None

        # only fire event if we have been logged in before
        if not self.login_error:
            self.__fire_login_state_changed()

    def __session_notify_main_thread(self, session=None):
        self.event_thread.process_events()

    # callbacks
    def __session_logged_in(self, session, error):
        logger.debug("logged_in, error: " + (error or "None"))

        if not error:
            self.playlist_container = session.playlist_container()
            self.is_logged_in = True
            self.login_error = None
        else:
            self.is_logged_in = False
            self.login_error = error

        self.__fire_login_state_changed()


    def __session_metadata_updated(self, session):
        done = []

        for index, obj in enumerate(self.metadata_waiters):
            if obj.check_is_loaded():
                # add to done list for deletion
                done.append(index)

                logger.debug("Metadata load detected")

        # remove all waiters that are done
        for index in reversed(done):
            del self.metadata_waiters[index]


    def __session_connection_error(self, session, error):
        logger.error('Connection error: %s', error)

    def __session_message_to_user(self, session, message):
        logger.info('Message to user: %s', message)

    def __session_music_delivery(self, session, frames, frame_size, num_frames, sample_type, sample_rate, channels):
        try:
            with self.audio_sink_lock:
                played_frames = self.audio.music_delivery(session, frames, frame_size, num_frames, sample_type, sample_rate, channels)

            played_seconds = float(played_frames) / float(sample_rate)

            self.track_playback_time += played_seconds

            # only fire every  second
            if self.track_playback_time - self.last_track_playback_time_notified >= 1:
                self.__fire_playback_progress_event()
                self.last_track_playback_time_notified = self.track_playback_time
                #print 'num_frames: {0}, frame_size: {1}'.format(num_frames, frame_size)

            return played_frames

        except Exception as e:
            logger.exception('Exception in music_delivery: %s', repr(e))
            return 0

    def __session_play_token_lost(self, session):
        logger.info('Play token lost')


    def __session_log_message(self, session, message):
        logger.debug('[Spotify] %s', message)

    def __session_end_of_track(self, session):
        # play next track
        if self.play_queue_mgr.move_next_track():
            self.__reinit_current_track()

    def __credentials_blob_updated(self, session, password_blob):
        def fire_event_command(session2, command_done):
            try:
                self.__fire_password_blob_changed(session2.username() if self.is_logged_in else None, password_blob)
            finally:
                command_done()

        # called from spotify internal thread, must be queued since we access session state (username)
        self.event_thread.enqueue_cmd(fire_event_command)

    # Private
    def __pause_player(self):
        self.session.play(0)
        self.is_playing = False

    def __start_player(self):
        self.session.play(1)
        self.is_playing = True

    def __reinit_current_track(self):
        self.track_playback_time = 0
        self.last_track_playback_time_notified = 0

        if self.current_track:
            self.__pause_player()
            self.current_track = None

        self.current_track = self.play_queue_mgr.get_current_track()


        if self.current_track:
            self.session.load(self.current_track.playable())
            self.__start_player()

        # fire event
        self.__fire_current_track_changed_event()
        self.__fire_player_state_changed_event()

    def __play_track_collection(self, track_collection, starting_track_uri):
        # replace queue
        self.play_queue_mgr.replace_queue(track_collection, starting_track_uri)

        # start playing track
        self.__reinit_current_track()

        # fire playqueue event
        self.__fire_playqueue_changed_event()


    # Events
    def __fire_player_state_changed_event(self):
        self.player_state_changed.fire(dict(
            is_repeat_on=self.play_queue_mgr.is_repeat_on,
            is_shuffle_on=self.play_queue_mgr.is_shuffle_on,
            is_playing=self.is_playing))

    def __fire_current_track_changed_event(self):
        self.current_track_changed.fire(self.current_track)

    def __fire_playback_progress_event(self):
        self.playback_progress.fire(self.track_playback_time)

    def __fire_playqueue_changed_event(self):
        self.playqueue_changed.fire()

    def __fire_login_state_changed(self):
        self.login_state_changed.fire(self.is_logged_in, self.login_error, self.session.username() if self.is_logged_in else None)

    def __fire_password_blob_changed(self, username, password_blob):
        self.password_blob_changed.fire(username, password_blob)




    # public API
    def start(self):
        if self.event_thread is not None:
            return

        self.event_thread = SpotifyEventThread(self.session)
        self.event_thread.start()

    def stop(self):
        def logout_command(session, command_done):
            try:
                session.logout()
            finally:
                command_done()

        if self.is_logged_in:
            # enqueue logout
            self.event_thread.enqueue_cmd(logout_command)

            # wait until logged out
            self.session_event_sink.wait_for('_manager_logged_out')

        # terminate thread and wait for all commands to finish
        self.event_thread.terminate()
        self.event_thread.join()
        self.event_thread = None

    def get_login_state(self, callback):
        def login_state_command(session, command_done):
            try:
                callback(self.is_logged_in, self.login_error, session.username() if self.is_logged_in else None)
            finally:
                command_done()

        self.event_thread.enqueue_cmd(login_state_command)


    def login(self, username, password, remember_me, password_blob, callback = None):
        def login_command(session, command_done):
            try:
                self.session.login(username, password or '', remember_me, password_blob)
            finally:
                command_done()

        def logged_in_event(session, error):
            if callback:
                callback(error)


        if self.is_logged_in:
            callback('Already logged in')
            return

        # subscribe for logged in event
        self.session_event_sink.subscribe_once('logged_in', logged_in_event)

        # enqueue login command
        self.event_thread.enqueue_cmd(login_command)


    def relogin(self):
        def relogin_command(session, command_done):
            try:
                self.session.relogin()
            except SpotifyError as e:
                self.__session_logged_in(session, str(e))
            finally:
                command_done()

        self.event_thread.enqueue_cmd(relogin_command)

    def get_player_state(self, callback):
        def get_player_state_command(session, command_done):
            try:
                callback(
                    self.current_track,
                    self.track_playback_time,
                    dict(
                        is_repeat_on=self.play_queue_mgr.is_repeat_on,
                        is_shuffle_on=self.play_queue_mgr.is_shuffle_on,
                        is_playing=self.is_playing))
            finally:
                command_done()

        self.event_thread.enqueue_cmd(get_player_state_command)


    def preview_link(self, uri, callback):
        def preview_link_command(session, command_done):
            def album_loaded(browser, album):
                callback(
                    LinkPreview(
                        '{0} - {1}'.format(album.artist().name(), album.name()),
                        'album',
                        binascii.hexlify(album.cover()),
                        uri))

            def playlist_loaded(playlist):
                callback(
                    LinkPreview(
                        playlist.name(),
                        'playlist',
                        None,
                        uri))

            def track_loaded(track):
                callback(
                    LinkPreview(
                        '{0} - {1}'.format(track.artists()[0].name() if len(track.artists()) > 0 else '', track.name()),
                        'track',
                        binascii.hexlify(track.album().cover()),
                        uri))


            try:
                link = Link.from_string(uri)
                link_type = link.type()

                if link_type == Link.LINK_ALBUM:
                    self.browse_album(uri, album_loaded)
                elif link_type == Link.LINK_PLAYLIST:
                    self.get_playlist(uri, playlist_loaded)
                elif link_type == Link.LINK_TRACK:
                    self.load_track(uri, track_loaded)
                else:
                    callback(None)

            finally:
                command_done()

        self.event_thread.enqueue_cmd(preview_link_command)




    def get_playqueue(self, callback):
        def get_playqueue_command(session, command_done):
            try:
                callback(self.play_queue_mgr.get_tracks())
            finally:
                command_done()

        self.event_thread.enqueue_cmd(get_playqueue_command)

    def get_playlists(self, callback):
        # got container?
        if self.playlist_container == None:
            callback([])

        def get_playlists_command(session, command_done):
            try:
                callback([(index, pl) for index, pl in enumerate(self.playlist_container) if pl.is_loaded() and pl.type() == 'playlist'])
            finally:
                command_done()

        self.event_thread.enqueue_cmd(get_playlists_command)

    def get_playlist(self, playlist_uri, callback):
        # got container?

        if self.playlist_container == None:
            callback(None)

        def get_playlist_command(session, command_done):
            try:

                playlist_link = Link.from_string(playlist_uri)
                playlist = playlist_link.as_playlist()
                if playlist.is_loaded() == 1:
                    callback(playlist)
                else:
                    callback(None)

            finally:
                command_done()

        self.event_thread.enqueue_cmd(get_playlist_command)




    def play_link(self, link_uri, starting_track_uri, callback = None):

        # inner async commands
        def change_playqueue_track_command(session, command_done):
            try:
                result = self.play_queue_mgr.change_track(starting_track_uri)
                if result:
                    self.__reinit_current_track()

                if callback:
                    callback(result)
            finally:
                command_done()


        def play_link_command(session, command_done):
            # async callbacks
            def album_loaded(browser, userdata):
                self.__play_track_collection(browser, starting_track_uri)
                if callback:
                    callback(True)

            def playlist_loaded(playlist):
                if playlist:
                    self.__play_track_collection(playlist, starting_track_uri)
                    if callback:
                        callback(True)

                else:
                    if callback:
                        callback(False)

            def track_loaded(track):
                self.__play_track_collection([ track ], starting_track_uri)
                if callback:
                    callback(True)

            try:
                link = Link.from_string(link_uri)

                if link.type() == Link.LINK_PLAYLIST:
                    self.get_playlist(link_uri, playlist_loaded)
                elif link.type() == Link.LINK_ALBUM:
                    self.browse_album(link_uri, album_loaded)
                elif link.type() == Link.LINK_TRACK:
                    self.load_track(link_uri, track_loaded)

            finally:
                command_done()

        if link_uri == 'playqueue':
            self.event_thread.enqueue_cmd(change_playqueue_track_command)
        else:
            self.event_thread.enqueue_cmd(play_link_command)



    def seek(self, offset, callback=None):
        def seek_command(session, command_done):
            try:
                self.__pause_player()

                # set current offset
                self.track_playback_time = offset
                self.last_track_playback_time_notified = 0

                self.__start_player()
                session.seek(offset * 1000)

                if callback:
                    callback()
            finally:
                command_done()


        self.event_thread.enqueue_cmd(seek_command)


    def play(self, callback=None):
        def play_command(sesson, command_done):
            try:
                self.__start_player()
                self.__fire_player_state_changed_event()

                if callback:
                    callback()
            finally:
                command_done()

        self.event_thread.enqueue_cmd(play_command)

    def pause(self, callback=None):
        def pause_command(sesson, command_done):
            try:
                self.__pause_player()
                self.__fire_player_state_changed_event()
                if callback:
                    callback()
            finally:
                command_done()

        self.event_thread.enqueue_cmd(pause_command)

    def next_track(self, callback=None):
        def next_track_command(sesson, command_done):
            try:
                if self.play_queue_mgr.move_next_track():
                    self.__reinit_current_track()

                if callback:
                    callback()
            finally:
                command_done()

        self.event_thread.enqueue_cmd(next_track_command)

    def previous_track(self, callback=None):
        def previous_track_command(sesson, command_done):
            try:
                if self.play_queue_mgr.move_previous_track():
                    self.__reinit_current_track()

                if callback:
                    callback()
            finally:
                command_done()

        self.event_thread.enqueue_cmd(previous_track_command)

    def set_shuffle(self, is_on, callback=None):
        def set_shuffle_command(sesson, command_done):
            try:
                self.play_queue_mgr.set_shuffle(is_on)

                self.__fire_player_state_changed_event()

                if callback:
                    callback()

                # fire playqueue event
                self.__fire_playqueue_changed_event()

            finally:
                command_done()

        self.event_thread.enqueue_cmd(set_shuffle_command)

    def set_repeat(self, is_on, callback=None):
        def set_repeat_command(sesson, command_done):
            try:
                self.play_queue_mgr.set_repeat(is_on)
                self.__fire_player_state_changed_event()

                if callback:
                    callback()
            finally:
                command_done()

        self.event_thread.enqueue_cmd(set_repeat_command)

    def search(self, query, callback, callback_userdata=None, track_offset=0, track_count=32, album_offset=0, album_count=32, artist_offset=0, artist_count=32, playlist_offset=0, playlist_count=32):
        def search_command(session, command_done):
            def search_callback(results, userdata):
                try:

                    callback(results, userdata)
                finally:
                    command_done()

            session.search(query=query,
                callback=search_callback,
                userdata=callback_userdata,
                track_offset = track_offset,
                track_count = track_count,
                album_offset = album_offset,
                album_count = album_count,
                artist_offset = artist_offset,
                artist_count = artist_count,
                playlist_offset = playlist_offset,
                playlist_count = playlist_count)

        self.event_thread.enqueue_cmd(search_command)

    def browse_album(self, album_uri, callback):
        def browse_album_command(sesson, command_done):
            def browse_album_callback(browser, userdata):
                try:
                    callback(browser, userdata)
                finally:
                    command_done()

            album_link = Link.from_string(album_uri)
            album = album_link.as_album()

            AlbumBrowser(album_link.as_album(), browse_album_callback, album)

        self.event_thread.enqueue_cmd(browse_album_command)

    def load_track(self, track_uri, callback):
        def load_track_command(sesson, command_done):
            def metadata_loaded_callback(track):
                try:
                    callback(track)
                finally:
                    command_done()

            track_link = Link.from_string(track_uri)
            track = track_link.as_track()

            async_load = AsyncLoadedItem(track, lambda x: x.is_loaded() == 1, metadata_loaded_callback)

            # first check if track is loaded, otherwise queue it for metadata watch
            if not async_load.check_is_loaded():
                self.metadata_waiters.append(async_load)

        self.event_thread.enqueue_cmd(load_track_command)


    def load_image(self, image_id, callback, callback_userdata=None):


        def load_image_command(session, command_done):
            timeout = 1
            start_time = time.time()
            elapsed_time = 0
            try:
                image = session.image_create(image_id)

                while not image.is_loaded() and elapsed_time < timeout:
                    if elapsed_time != 0:
                        logger.debug('Image still not loaded after %s sec', elapsed_time)
                    elapsed_time = time.time() - start_time
                    time.sleep(0.1)
                    self.session.process_events()

                if image.is_loaded():
                    callback(image, callback_userdata)
                else:
                    print 'image error: ' + str(image.error())
                    callback(None, callback_userdata)

            finally:
                command_done()

        self.event_thread.enqueue_cmd(load_image_command)











