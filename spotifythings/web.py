import os.path
import binascii
import json
import logging

# tornado
import tornado.web
import tornado.ioloop
import tornado.websocket
from tornado.httpclient import AsyncHTTPClient

# spotify
from spotify import Link

logger = logging.getLogger(__name__)

class BaseHandler(tornado.web.RequestHandler):
    pass



class SearchJsonHandler(BaseHandler):

    def initialize(self, spotify_session):
        self.spotify_session = spotify_session


    @tornado.web.asynchronous
    def get(self):
        query = self.get_argument("q", None)
        track_offset = int(self.get_argument("to", 0));
        album_offset = int(self.get_argument("ao", 0));
        track_count = int(self.get_argument("tc", 10));
        album_count = int(self.get_argument("ac", 10));

        self.spotify_session.search(
            query = query,
            callback = self.search_finished,
            callback_userdata = query,
            track_count = track_count,
            track_offset = track_offset,
            album_count = album_count,
            album_offset = album_offset,
            playlist_count = 0,
            artist_count = 0)

    def search_finished(self, results, userdata):

        albums = [{
            'album_name': x.name(),
            'artist_name':x.artist().name(),
            'image_id': binascii.hexlify(x.cover()),
            'link': str(Link.from_album(x))} for x in results.albums()]

        tracks = [{
            'track_name': track.name(),
            'artists': [artist.name() for artist in track.artists()],
            'duration': track.duration(),
            'popularity': track.popularity(),
            'album': track.album().name(),
            'is_available': track.availability() == 1,
            'link': str(Link.from_track(track))
            } for track in results.tracks() if track.availability() == 1]


        self.write(dict(
            albums = albums,
            total_albums = results.total_albums(),
            tracks = tracks,
            total_tracks = results.total_tracks(),
            query = results.query()))

        self.finish()

class AlbumInfoJsonHandler(BaseHandler):

    def initialize(self, spotify_session):
        self.spotify_session = spotify_session


    @tornado.web.asynchronous
    def get(self, album_uri):
        self.spotify_session.browse_album(album_uri, self.album_loaded)

    def album_loaded(self, browser, album):
        discs = dict()

        for track in browser:
            disc = track.disc()
            if disc not in discs:
                discs[disc] = []

            discs[disc].append(track)

        arist = album.artist().name()

        self.write(dict(
            album_name = album.name(),
            artist = arist,
            type = album.type(),
            year = album.year(),
            link = str(Link.from_album(album)),
            discs = [{
                'disc': discno,
                'tracks': [{
                    'track_name': x.name(),
                    'track_index': x.index(),
                    'duration': x.duration(),
                    'link': str(Link.from_track(x)),
                    'is_available': track.availability() == 1,
                    'artists': [artist.name() for artist in x.artists()] } for x in tracks]} for discno, tracks in discs.iteritems()]))


        self.finish()


class PlaylistsJsonHandler(BaseHandler):

    def initialize(self, spotify_session):
        self.spotify_session = spotify_session

    @tornado.web.asynchronous
    def get(self):
        def playlists_received(playlists):
            self.write(dict(result=[{
                'track_count': len(pl),
                'name': pl.name(),
                'link': str(Link.from_playlist(pl))} for (index, pl) in playlists]))
            self.finish()

        self.spotify_session.get_playlists(playlists_received)

class PlayQueueHandler(BaseHandler):

    def initialize(self, spotify_session):
        self.spotify_session = spotify_session

    @tornado.web.asynchronous
    def get(self):
        def playqueue_callback(playqueue):
            self.write(dict(result=[{
                    'track_name': track.name(),
                    'duration': track.duration(),
                    'link': str(Link.from_track(track)),
                    'is_available': track.availability() == 1,
                    'artists': [artist.name() for artist in track.artists()] } for track in playqueue]))
            self.finish()

        self.spotify_session.get_playqueue(playqueue_callback)

class TrackInfoJsonHandler(BaseHandler):

    def initialize(self, spotify_session):
        self.spotify_session = spotify_session

    @tornado.web.asynchronous
    def get(self, track_uri):
        def track_loaded(track):
            self.write(dict(
                name=track.name(),
                link=str(Link.from_track(track))))

            self.finish()

        self.spotify_session.load_track(track_uri, track_loaded)

class PlaylistInfoJsonHandler(BaseHandler):

    def initialize(self, spotify_session):
        self.spotify_session = spotify_session

    @tornado.web.asynchronous
    def get(self, link):
        def playlist_received(playlist):
            if not playlist:
                self.set_status(404)
            else:
                self.write(dict(
                    name=playlist.name(),
                    link=str(Link.from_playlist(playlist)),
                    tracks = [{
                        'track_name': track.name(),
                        'duration': track.duration(),
                        'link': str(Link.from_track(track)),
                        'is_available': track.availability() == 1,
                        'artists': [artist.name() for artist in track.artists()] } for track in playlist]))

            self.finish()

        self.spotify_session.get_playlist(link, playlist_received)

class RfidLinkStatusHandler(BaseHandler):
    def initialize(self, store):
        self.store = store

    def get(self, link):
        tags = self.store.find_tags_by_link(link)
        self.write(dict(tags = tags))

class RfidTagsHandler(BaseHandler):
    def initialize(self, store):
        self.store = store

    def get(self):
        self.write(dict(
            result=[{
                'image_id': tag.imageid,
                'link': tag.spotifylink,
                'type': tag.linktype,
                'name': tag.name,
                'tag': tag.rfidtag
            } for tag in self.store.find_all_tags()]))

class RfidTagHandler(BaseHandler):
    def initialize(self, store, spotify_session):
        self.store = store
        self.spotify_session = spotify_session


    def delete(self, tag):
        rowsdeleted = self.store.delete_tag(tag)
        if rowsdeleted == 0:
            self.set_status(404, 'Tag not found')

    @tornado.web.asynchronous
    def put(self, tag):
        def link_resolved(preview):
            if preview:
                self.store.add_tag(tag, preview.uri, preview.type, preview.image_id, preview.name)
            else:
                self.set_status(500)

            self.finish()

        uri = self.request.body
        self.spotify_session.preview_link(uri, link_resolved)

    @tornado.web.asynchronous
    def post(self, tag):
        def link_resolved(preview):
            if preview:
                self.store.update_tag(tag, preview.uri, preview.type, preview.image_id, preview.name)
            else:
                self.set_status(500)
            self.finish()

        uri = self.request.body
        self.spotify_session.preview_link(uri, link_resolved)

class ImageHandler(BaseHandler):

    def initialize(self, spotify_session):
        self.spotify_session = spotify_session


    @tornado.web.asynchronous
    def get(self, id):
        def image_loaded(image, userdata):
            if image:
                data = image.data()
                if data:
                    self.set_header('Content-type', 'image/jpeg')
                    self.set_header('Content-length', str(len(data)))
                    self.write(str(data))
                else:
                    self.set_status(404)
            else:
                self.set_status(404)

            self.finish()

        image_id = binascii.unhexlify(id)

        self.spotify_session.load_image(image_id, image_loaded, id)









class SpotifyCredentialsHandler(BaseHandler):

    def initialize(self, spotify_session, app):
        self.spotify_session = spotify_session
        self.app = app


    @tornado.web.asynchronous
    def put(self):
        def logged_in(error):
            self.write(dict(success = not error, error = error))
            self.finish()

        username = self.get_argument('username')
        password = self.get_argument('password')

        self.spotify_session.login(username, password, False, None, logged_in)

    def delete(self):
        self.app.forget_spotify_credentials()


class RfidWebSocket(tornado.websocket.WebSocketHandler):
    def initialize(self, wsregistry):
        self.wsregistry = wsregistry

    def open(self):
        self.wsregistry.register_ws('rfid', self)
        logger.debug('[RFID] new connection')

    def on_message(self, message):
        logger.debug('[RFID] message received %s',  message)

    def on_close(self):
        self.wsregistry.unregister_ws('rfid', self)
        logger.debug('[RFID] connection closed')


class ApplicationWebSocket(tornado.websocket.WebSocketHandler):

    def initialize(self, spotify_session, wsregistry):
        self.spotify_session = spotify_session
        self.wsregistry = wsregistry

    def open(self):
        self.wsregistry.register_ws('app', self)
        logger.debug('[Application] new connection')

    def send_error(self, error_data):
        self.write_message(dict(type='error', data=error_data))


    def on_message(self, message):
        msg = json.loads(message)


        optype = msg['type']



        data = msg['data'] if 'data' in msg else None

        if optype == 'player.play':
            self.spotify_session.play()
        elif optype == 'player.pause':
            self.spotify_session.pause()
        elif optype == 'player.set_repeat':
            self.spotify_session.set_repeat(data)
        elif optype == 'player.set_shuffle':
            self.spotify_session.set_shuffle(data)
        elif optype == 'player.next_track':
            self.spotify_session.next_track()
        elif optype == 'player.previous_track':
            self.spotify_session.previous_track()
        elif optype == 'player.seek':
            self.spotify_session.seek(data)
        elif optype == 'player.play_track':
            self.spotify_session.play_link(data['resource_link'], data['track_link'])
        else:
            self.write_message(dict(type='error', data='unknown message type {0}'.format(optype)))



    def on_close(self):
        self.wsregistry.unregister_ws('app', self)
        logger.debug('[Application] connection closed')


class WebApplication(tornado.web.Application):

    def __init__(self, app):
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), 'www', 'templates'),
            static_path=os.path.join(os.path.dirname(__file__), 'www', 'static'),
            debug = True
        )

        handlers = [
            # json api's
            (r"/api/search", SearchJsonHandler, dict(spotify_session = app.spotify_session)),
            (r"/api/playlist", PlaylistsJsonHandler, dict(spotify_session = app.spotify_session)),
            (r"/api/playlist/(.+)", PlaylistInfoJsonHandler, dict(spotify_session = app.spotify_session)),
            (r"/api/playqueue", PlayQueueHandler, dict(spotify_session = app.spotify_session)),
            (r"/api/album/(spotify:album:\w+)", AlbumInfoJsonHandler, dict(spotify_session = app.spotify_session)),
            (r"/api/track/(spotify:track:\w+)", TrackInfoJsonHandler, dict(spotify_session = app.spotify_session)),
            (r"/api/rfid-linkstatus/(spotify:.+)", RfidLinkStatusHandler, dict(store=app.store)),
            (r"/api/rfid/(\w+)", RfidTagHandler, dict(store=app.store, spotify_session=app.spotify_session)),
            (r"/api/rfid", RfidTagsHandler, dict(store=app.store)),
            (r"/api/credentials", SpotifyCredentialsHandler, dict(spotify_session = app.spotify_session, app=app)),


            # websockets
            (r'/ws/rfid', RfidWebSocket, dict(wsregistry = app.wsregistry)),
            (r'/ws/app', ApplicationWebSocket, dict(wsregistry = app.wsregistry, spotify_session = app.spotify_session)),


            # frontend
            (r"/image/([0-9a-fA-F]+)", ImageHandler, dict(spotify_session = app.spotify_session)),


            # static
            (r'/static/(.*)', tornado.web.StaticFileHandler)]

        super(WebApplication, self).__init__(handlers, **settings)





