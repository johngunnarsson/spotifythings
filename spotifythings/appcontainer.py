# -*- coding: utf-8 -*-
import time
import logging

from persistentstore import PersistentStore
from asyncioloop import AsyncIOLoop
from websocket_registry import WebSocketRegistry
from wsmessage import *

from Phidgets.PhidgetException import PhidgetErrorCodes, PhidgetException
from Phidgets.Events.Events import AttachEventArgs, DetachEventArgs, ErrorEventArgs, OutputChangeEventArgs, TagEventArgs
from Phidgets.Devices.RFID import RFID, RFIDTagProtocol

from web import WebApplication
from asyncsession import SpotifyAsyncSessionManager
import tornado.web

logger = logging.getLogger(__name__)

class RfidReader(object):
    def __init__(self, name, version, serial_no):
        self.name = name
        self.version = version
        self.serial_no = serial_no


class AppContainer(object):

    def __init__(self, config):
        self.config = config
        self.store = PersistentStore(self.config['dbfilename'])


        self.spotify_session = SpotifyAsyncSessionManager(useragent="SpotifyThings")
        self.spotify_session.player_state_changed += self.__player_state_changed
        self.spotify_session.current_track_changed += self.__current_track_changed
        self.spotify_session.playback_progress += self.__playback_progress_event
        self.spotify_session.playqueue_changed += self.__playqueue_changed_event
        self.spotify_session.login_state_changed += self.__login_state_changed_event
        self.spotify_session.password_blob_changed += self.__login_password_blob_changed

        self.wsregistry = WebSocketRegistry();
        self.wsregistry.on_new_client += self.__on_new_client

        self.webapp = WebApplication(self)
        self.asyncioloop = AsyncIOLoop()

        self.attached_rfid_readers = dict()

        self.rfid = RFID()
        self.rfid.setOnAttachHandler(self.rfidAttached)
        self.rfid.setOnDetachHandler(self.rfidDetached)
        self.rfid.setOnErrorhandler(self.rfidError)
        self.rfid.setOnTagHandler(self.rfidTagGained)
        self.rfid.setOnTagLostHandler(self.rfidTagLost)



    # player events
    def __player_state_changed(self, state):
        self.wsregistry.broadcast('app', PlayerStateMessage(state))

    def __current_track_changed(self, track):
        self.wsregistry.broadcast('app', PlayerCurrentTrackMessage(track))

    def __playback_progress_event(self, playback_time):
        self.wsregistry.broadcast('app', PlayerPlaybackProgressMessage(int(playback_time)))

    def __playqueue_changed_event(self):
        self.wsregistry.broadcast('app', PlayerQueueModifiedMessage())

    # app event
    def __login_state_changed_event(self, is_logged_in, login_error, current_user):
        self.wsregistry.broadcast('app', SpotifyLoginStateMessage(is_logged_in, login_error, current_user))

    def __login_password_blob_changed(self, username, password_blob):
        self.store.set_config('spotify.username', username)
        self.store.set_config('spotify.password_blob', password_blob)

        self.wsregistry.broadcast('app', SpotifyCredentialStoredMessage(self.store.get_config('spotify.password_blob') is not None))

    # websocket events
    def __on_new_client(self, wstype, ws):
        def spotify_state_handler(current_track, track_playback_time, player_state):
            # send player state
            ws.write_message(PlayerStateMessage(player_state))

            # send current track
            ws.write_message(PlayerCurrentTrackMessage(current_track))

            # send playback progress
            ws.write_message(PlayerPlaybackProgressMessage(int(track_playback_time)))

        def spotify_login_state_handler(is_logged_in, login_error, current_user):
            # send login state message
            ws.write_message(SpotifyLoginStateMessage(is_logged_in, login_error, current_user))

        if wstype == "app":
            # request spotify state
            self.spotify_session.get_player_state(spotify_state_handler)

            # request login state
            self.spotify_session.get_login_state(spotify_login_state_handler)

            # send message with currently attched rfid readers
            ws.write_message(RfidReaderUpdatedMessage(self.attached_rfid_readers))

            # send message with credentials stored status
            ws.write_message(SpotifyCredentialStoredMessage(self.store.get_config('spotify.password_blob') is not None))


    # rfid events
    def rfidAttached(self, e):
        device = e.device
        device.setAntennaOn(True)

        # add to list of attached readers
        reader = RfidReader(
            device.getDeviceName(),
            device.getDeviceVersion(),
            device.getSerialNum())

        self.attached_rfid_readers[reader.serial_no] = reader

        # notify clients
        self.wsregistry.broadcast('app', RfidReaderUpdatedMessage(self.attached_rfid_readers))

        logger.info('RFID reader %s Attached', device.getSerialNum())


    def rfidDetached(self, e):
        device = e.device
        serial_no = device.getSerialNum()

        # remove from attached list
        del self.attached_rfid_readers[serial_no]

        # notify clients
        self.wsregistry.broadcast('app', RfidReaderUpdatedMessage(self.attached_rfid_readers))

        logger.info('RFID reader %s Deteched', device.getSerialNum())


    def rfidError(self, e):
        try:
            source = e.device

            logger.error("RFID %i: Phidget Error %i: %s", source.getSerialNum(), e.eCode, e.description)
        except PhidgetException as e:
            logger.exception('Phidget Exception %i: %s', e.code, e.details)

    def rfidTagGained(self, e):
        source = e.device
        self.rfid.setLEDOn(1)
        logger.debug('RFID %i: Tag Read: %s', source.getSerialNum(), e.tag)


        # get existing mapping, if any
        tagmapping = self.store.find_by_tagid(e.tag)

        # broadcast to any listeners
        any_listeners = self.wsregistry.broadcast('rfid', RfidTagReadMessage(e.tag, tagmapping))

        # no listeners and resource was mapped, play resource
        if not any_listeners and tagmapping:
            self.spotify_session.play_link(tagmapping.spotifylink, None)

    def rfidTagLost(self, e):
        source = e.device
        self.rfid.setLEDOn(0)
        logger.debug('RFID %i: Tag Lost: %s', source.getSerialNum(), e.tag)


    def forget_spotify_credentials(self):
        # delete from store
        self.store.delete_configs(['spotify.username', 'spotify.password_blob'])

        # notify clients
        self.wsregistry.broadcast('app', SpotifyCredentialStoredMessage(self.store.get_config('spotify.password_blob') is not None))



    def start(self):
        logger.info('Starting appcontainer')

        # initialize store
        logger.info('Initializing store')
        self.store.initialize()

        # start spotify
        logger.info('Starting spotify session')
        self.spotify_session.start()

        # login using stored credentials
        username = self.store.get_config('spotify.username')
        password_blob = self.store.get_config('spotify.password_blob')

        if username and password_blob:
            logger.info('Logging in with username %s', username)
            self.spotify_session.login(username, None, False, password_blob)

        # start webapp
        listen_port = self.config['listen_port']
        logger.info('Starting web application, listening on port %s', listen_port)
        self.webapp.listen(listen_port)
        self.asyncioloop.start()

        # start rfid
        logger.info('Initializing RFID reader')
        self.rfid.openPhidget()

        logger.info('Appcontainer started')

    def stop(self):
        logger.info('Stopping appcontainer')

        # stop rfid
        logger.info('Closing RFID reader')
        self.rfid.closePhidget()

        # stop webapp
        logger.info('Stopping web application')
        self.asyncioloop.stop()

        # stop spotify
        logger.info('Stopping Spotify session')
        self.spotify_session.stop()

        logger.info('Appcontainer stopped')


