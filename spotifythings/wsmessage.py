# -*- coding: utf-8 -*-
import binascii
from spotify import Link

class PlayerStateMessage(dict):
     def __init__(self, state):
         super(PlayerStateMessage, self).__init__(type='player.state', data=state)


class PlayerCurrentTrackMessage(dict):
    def __init__(self, track):
        super(PlayerCurrentTrackMessage, self).__init__(
            type='player.current_track',
            data=dict(
                name = track.name(),
                artists = ", ".join([artist.name() for artist in track.artists()]),
                link = str(Link.from_track(track)),
                duration = track.duration(),
                image_id = binascii.hexlify(track.album().cover())) if track else None)


class PlayerPlaybackProgressMessage(dict):
     def __init__(self, playback_time):
         super(PlayerPlaybackProgressMessage, self).__init__(type='player.playback_progress', data=playback_time)


class PlayerQueueModifiedMessage(dict):
     def __init__(self):
         super(PlayerQueueModifiedMessage, self).__init__(type='player.queue_modified')

class SpotifyLoginStateMessage(dict):
     def __init__(self, is_logged_in, login_error, current_user):
         super(SpotifyLoginStateMessage, self).__init__(
             type='spotify.login_state',
             data = dict(is_logged_in=is_logged_in, login_error=login_error, current_user=current_user))

class SpotifyCredentialStoredMessage(dict):

     def __init__(self, is_stored):
         super(SpotifyCredentialStoredMessage, self).__init__(
             type='spotify.credentials_stored',
             data = is_stored)


class RfidTagReadMessage(dict):
     def __init__(self, tag, tagmapping):
         super(RfidTagReadMessage, self).__init__(type='tag_read', tag=tag, previous_association=tagmapping.name if tagmapping else None)


class RfidReaderUpdatedMessage(dict):
     def __init__(self, readers):
         super(RfidReaderUpdatedMessage, self).__init__(
             type='hardware.rfid_reader', data = [dict(name=v.name, serial_no = v.serial_no, version=v.version) for k, v in readers.iteritems()])



