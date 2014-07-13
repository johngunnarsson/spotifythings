function log(msg) {
    console.log(msg);
}


var adminServices = angular.module('adminServices', []);

adminServices.service('HostService', function() {
    this.hostname = window.location.hostname + ':' + window.location.port;
});


adminServices.service('CoverService', function($timeout) {



    this.createCoverUrlProxy = function (spotifyUrl) {
        var MISSING_COVER_URL = '/static/image/missing-album-lg.png';
        var state = {
            url: MISSING_COVER_URL,
            request_started: false
        };

        return function () {

            // check if we should initialize the request
            if (!state.request_started && spotifyUrl != null) {

                // update state
                state.request_started = true;

                // perform the ajax request
                $.ajax({
                    url: "https://embed.spotify.com/oembed/",
                    jsonp: "callback",
                    dataType: "jsonp",
                    data: {
                        url: spotifyUrl
                    },
                    cache: true,
                    success: function( response ) {

                        $timeout(function () {
                            // update url
                            state.url = response.thumbnail_url;
                        });
                    }
                });
            }

            return state.url;
        };
    };


    this.loadCover = function(url, callback) {

    };

});

adminServices.service('SpotifyService', function($http, MessageService) {

         this.search = function (query, track_count, album_count, track_offset, album_offset, callback) {

            $http.get('/api/search', { params: { q: query, tc: track_count, ac: album_count, to: track_offset, ao: album_offset }}).success(function(data) {
                callback(data);
            });	
	};
	
	this.getAlbumInfo = function(link, callback) {

	   $http.get('/api/album/' + link).success(function(data) {
                callback(data);
            });
        };

        this.getPlaylists = function(callback) {
            $http.get('/api/playlist').success(function(data) {
                callback(data.result);
            });

        };

        this.getPlaylistInfo = function (link, callback) {
            $http.get('/api/playlist/' + link).success(function(data) {
                callback(data);
            });
        };

        this.getPlayQueue = function (callback) {
            $http.get('/api/playqueue').success(function(data) {
                callback(data.result);
            });
        };

        this.getTrackInfo = function (link, callback) {
            $http.get('/api/track/' + link).success(function(data) {
                callback(data);
            });
        };

        this.login = function (username, password, callback) {
            $http.put(
                '/api/credentials',
                { username: username, password: password },
                { headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}, transformRequest: $.param }
            ).success(function(response) {
                callback(response);
            });
        };

        this.logout = function (callback) {
            $http.delete('/api/credentials').success(function() {
                callback();
            });	
	};


        this.subscribeLoginState = function (handler) {
            return MessageService.subscribe('spotify.login_state', handler, true);
        };

        this.subscribeCredentialsStored = function (handler) {
            return MessageService.subscribe('spotify.credentials_stored', handler, true);
        };
	
});


adminServices.service('RFIDTagService', function($http, MessageService) {

         this.getLinkStatus = function (link, callback) {

            $http.get('/api/rfid-linkstatus/' + link).success(function(data) {
                callback(data);
            });	
	};
	
	this.unlinkTag = function (tag, callback) {

            $http.delete('/api/rfid/' + tag).success(function() {
                callback();
            });	
	};
	
	
	this.linkTag = function (tag, spotifyLink, callback) {
            $http.put('/api/rfid/' + tag, spotifyLink).success(function() {
                callback();
            });	
	};
	
	this.relinkTag = function (tag, spotifyLink, callback) {

            $http.post('/api/rfid/' + tag, spotifyLink).success(function() {
                callback();
            });	
	};
	
	this.getAll = function(callback) {
            $http.get('/api/rfid').success(function(data) {
                callback(data.result);
            });

         };


         this.subscribeAttachedReaders = function (handler) {
            return MessageService.subscribe('hardware.rfid_reader', handler, true);
        };
	
	
	
});


adminServices.service('MessageService', function($http, $rootScope, $timeout, HostService, AlertService) {

    var lastMessage = {};


    function setLastMessage(messageType, payload) {
        lastMessage[messageType] = payload;
    }

    function getLastMessage(messageType) {
        return messageType in lastMessage ? lastMessage[messageType] : null;
    }


    var ws =  new WebSocket('ws://' + HostService.hostname + '/ws/app');

    this.sendMessage = function (type, data) {
        ws.send(JSON.stringify({'type': type, data: data }));
    };

    this.subscribe = function (messageType, handler, propagateLastMessage) {
        if (propagateLastMessage) {
            var lastMessage = getLastMessage(messageType);
            if (lastMessage) {
                handler(lastMessage);
            }
        }

        return $rootScope.$on(messageType, function(e, data) {
            handler(data);
        });
    };


    this.replayLastMessage = function (messageType, handler) {
        var lastMessage = getLastMessage(messageType);
        if (lastMessage)
            handler(lastMessage);
    };


    ws.onmessage = function (evt) {
        log(evt.data);


        var message = $.parseJSON(evt.data);
        var type = message.type;
        var payload = message.data;

        // save message
        setLastMessage(type, payload);

        // emit message
        $timeout(function () {
            $rootScope.$emit(type, payload);
        });

    };

    ws.onerror = function (error) {
        AlertService.error('WebSocket error:' + error);
    };

    ws.onclose = function (evt) {
        ws = null;
    };

});



adminServices.service('PlayerService', function($http, $rootScope, MessageService) {


    this.playTrack = function(resource_link, track_link) {
        MessageService.sendMessage('player.play_track', { resource_link: resource_link, track_link: track_link});
    };

    this.play = function() {
        MessageService.sendMessage('player.play');
    };

    this.pause = function() {
        MessageService.sendMessage('player.pause');
    };

    this.nextTrack = function() {
        MessageService.sendMessage('player.next_track');
    };

    this.previousTrack = function() {
        MessageService.sendMessage('player.previous_track');
    };

    this.setRepeat = function(isOn) {
        MessageService.sendMessage('player.set_repeat', isOn);
    };

    this.setShuffle = function(isOn) {
        MessageService.sendMessage('player.set_shuffle', isOn);
    };

    this.seek = function(offset) {
        MessageService.sendMessage('player.seek', offset)
    }


    // subcribtions
    this.updatePlayerState = function(handler) {
        MessageService.replayLastMessage('player.state', handler);
    };

    this.subscribePlayerState = function(handler) {
        return MessageService.subscribe('player.state', handler, true);
    };

    this.subscribePlayQueueChanged = function(handler) {
        return MessageService.subscribe('player.queue_modified', handler, false);
    };

    this.updateCurrentTrackPlaying = function(handler) {
        MessageService.replayLastMessage('player.current_track', handler);
    };

    this.subscribeCurrentTrackPlaying = function(handler) {
        return MessageService.subscribe('player.current_track', handler, true);
    };

    this.subscribePlaybackProgress = function(handler) {
        return MessageService.subscribe('player.playback_progress', handler, true);
    };

    this.subscribeError = function(handler) {
        return MessageService.subscribe('error', handler, false);
    };

});


adminServices.service('AlertService', function($rootScope) {
    var alertSequence = 0;

    function publishAlert(type, msg) {
        $rootScope.$emit('alert', { type: type, message: msg });
    }

    this.info = function (msg) {
        publishAlert('info', msg);
    };

    this.error = function (msg) {
        publishAlert('error', msg);
    };

    this.subscibeAlerts = function (handler) {
        return $rootScope.$on('alert', function(e, data) {
            handler(++alertSequence, data.type, data.message);
        });
    };


});