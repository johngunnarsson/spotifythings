


// controllers
var adminControllers = angular.module('adminControllers', ['adminServices']);


adminControllers.controller('AppCtrl', function ($scope, $location, SpotifyService, AlertService, RFIDTagService) {

    $scope.alerts = [];

    $scope.closeAlert = function(alertId) {
        for (var i = 0; i < $scope.alerts.length; i++) {
            var alert = $scope.alerts[i];

            if (alert.id == alertId) {
                $scope.alerts.splice(i, 1);
            }
        }
    };

    // helper for determinate if a menuitem is active
    $scope.isActive = function (url) {
        return url == $location.path();
    };

    $scope.isSpotifyLoggedIn = false;


    // subscribe on login state
    $scope.$on('$destroy',
        SpotifyService.subscribeLoginState(function (state) {
            $scope.isSpotifyLoggedIn = state.is_logged_in;
        })
    );	



    // subscribe for alerts
    $scope.$on('$destroy',
        AlertService.subscibeAlerts(function (sequence, type, message) {
            $scope.alerts.push({id: sequence, type: type, message: message});
        })
    );	
		
});

adminControllers.controller('SearchCtrl', function ($scope, $rootScope, SpotifyService, PlayerService, CoverService) {

    function initializeCoverUrls(albums) {
        for (var i = 0; i < albums.length; i++)
            albums[i].coverUrl = CoverService.createCoverUrlProxy(albums[i].link);
    }

    $scope.trackPlayer = new TrackCollectionPlayer(PlayerService);
    $scope.$on('$destroy', $scope.trackPlayer.destroy);
	
	$scope.tracks = [];
	$scope.albums = [];
	$scope.totalTracks = 0;
	$scope.totalAlbums = 0;
	$scope.hasMoreTracks = false;
         $scope.hasMoreAlbums = false;
         $scope.lastSearchTerm = null;
         $scope.searchInProgress = false;
	
	var TRACKS_PAGING_SIZE = 50;
	var ALBUMS_PAGING_SIZE = 32;
	
	
	function updateHasMore() {
            $scope.hasMoreTracks = $scope.tracks.length < $scope.totalTracks;
            $scope.hasMoreAlbums = $scope.albums.length < $scope.totalAlbums;
         }
	
	$scope.search = function () {
	    $scope.searchInProgress = true;

            SpotifyService.search($scope.query, TRACKS_PAGING_SIZE, ALBUMS_PAGING_SIZE, 0, 0, function (data) {
                $scope.searchInProgress = false;
                $scope.tracks.length = 0;
                $scope.albums.length = 0;

                // create proxy for lazyloading url
                initializeCoverUrls(data.albums);


                $scope.tracks.push.apply($scope.tracks, data.tracks);
                $scope.albums.push.apply($scope.albums, data.albums);

                $scope.totalTracks = data.total_tracks;
	       $scope.totalAlbums = data.total_albums;

                // save last search, used for paging
                $scope.lastSearchTerm = data.query;

                updateHasMore();

            });
        };

        $scope.inputKeyPress = function($event) {
            if ($event.keyCode == 13)
                $scope.search();
        };

        $scope.showMoreTracks = function () {
            SpotifyService.search($scope.lastSearchTerm, TRACKS_PAGING_SIZE, 0, $scope.tracks.length, 0, function (data) {
                $scope.tracks.push.apply($scope.tracks, data.tracks);

                updateHasMore();
            })
        };

        $scope.showMoreAlbums = function () {
            SpotifyService.search($scope.lastSearchTerm, 0, ALBUMS_PAGING_SIZE, 0, $scope.albums.length, function (data) {
                // create proxy for lazyloading url
                initializeCoverUrls(data.albums);

                $scope.albums.push.apply($scope.albums, data.albums);

                updateHasMore();
            });
        }


    $scope.albumGrid = new GridHelper(4, $scope.albums);

    $scope.showAlbumInfo = function (link) {
        $rootScope.$emit('show-album-info', link);
    };

    $scope.showTrackInfo = function (link) {
        $rootScope.$emit('show-track-info', link);
    };
	

});

adminControllers.controller('AlbumInfoCtrl', function ($scope, $rootScope, $element, SpotifyService, PlayerService) {


    $scope.player = new TrackCollectionPlayer(PlayerService);
    $scope.$on('$destroy', $scope.player.destroy);

    $element.on('hide.bs.modal', function (e) {
        $scope.$broadcast('container-hidden');
    });

	
    var unbind = $rootScope.$on('show-album-info', function(e, link) {

        SpotifyService.getAlbumInfo(link, function (album) {

            // post process album data structure
            for (var discIndex = 0; discIndex < album.discs.length; discIndex++) {
                var disc = album.discs[discIndex];

                disc.containsOtherArtists = false;

                for (var trackIndex = 0; trackIndex < disc.tracks.length; trackIndex++) {
                    var track = disc.tracks[trackIndex];

                    track.artist_str = track.artists.join(', ');


                    if (track.artist_str == album.artist) {
                        track.artist_str = '';
                    } else {
                        disc.containsOtherArtists = true;
                    }
                }



            }

            $scope.album = album;

            $scope.player.refresh();

            $element.modal('show');

        });

        $rootScope.$emit('init-rfid-status', link);


    });




    $scope.$on('$destroy', unbind);
		
});


adminControllers.controller('RFIDCtrl', function ($scope, $rootScope, RFIDTagService, HostService, AlertService) {
    $scope.activeView = '';
    $scope.ws = null;
    $scope.tags = null;
    $scope.link = null;
    $scope.overwriteTag = null;


    $scope.switchToStatusMode = function (reload) {

        $scope.closeWebSocket();

        if (reload || !$scope.tags) {
            RFIDTagService.getLinkStatus($scope.link, function (data) {
                $scope.tags = data.tags;
                $scope.activeView = 'current-status.html';
            });
        } else {
            $scope.activeView = 'current-status.html';
        }




    };

    $scope.switchToAssociationMode = function () {
        $scope.activeView = 'waiting-tag.html';
        $scope.overwriteTag = false;


        var ws =  new WebSocket('ws://' + HostService.hostname + '/ws/rfid');	

        ws.onopen = function() {


        };

        ws.onmessage = function (evt) {
           $scope.$apply(function () {
               var msg = $.parseJSON(evt.data);

               if (msg.type == 'tag_read') {
                    if (msg.previous_association) {
                        $scope.overwriteTag = { name: msg.previous_association, tag: msg.tag };
                    }
                    else {
                        // no previous association, autolink
                        RFIDTagService.linkTag(msg.tag, $scope.link, function () {
                            $scope.tags.push(msg.tag);
                            $scope.switchToStatusMode();
                        });
                    }
                }
            });
        };

        ws.onerror = function (error) {
            AlertService.error('WebSocket error:' + error);
        };

        ws.onclose = function (evt) {
            $scope.ws = null;
        };

        $scope.ws = ws;
    };



    $scope.closeWebSocket = function () {
        if ($scope.ws) {
            $scope.ws.close();
            $scope.ws = null;
        }

    };

    $scope.relinkTag = function (tag) {
        RFIDTagService.relinkTag(tag, $scope.link, function () {
            $scope.switchToStatusMode(true);

        });
    };

    $scope.unlinkTag = function (tag) {
        RFIDTagService.unlinkTag(tag, function () {
            // tag removed serverside, remove from list
            var index = $.inArray(tag, $scope.tags);
            if (index != -1)
                $scope.tags.splice(index, 1);
        });
    };


    // event for initializing controller
    $scope.$on('$destroy',
        $rootScope.$on('init-rfid-status', function(e, link) {
            $scope.activeView = '';
            $scope.link = link;
            $scope.switchToStatusMode(true);
        }));

    // event for cleaning up websockets when modal is closed
    $scope.$on('$destroy',
        $scope.$on('container-hidden', function() {
            $scope.closeWebSocket();
        }));


    // cleanup when controller dies	
    $scope.$on('$destroy', function () {
        $scope.closeWebSocket();
    });
	
		
});


adminControllers.controller('PlayerCtrl', function ($scope, PlayerService, AlertService) {

    var isSliding = false;

    function start_slide(ev, ui) {
        isSliding = true;
    }

    function stop_slide(ev, ui) {
        isSliding = false;

        //PlayerService.seek(ui.value);
    }

    $scope.trackProgress = 0;
    $scope.trackLength = 0;
    $scope.playbackOptions = {
        start: start_slide,
        stop: stop_slide
    };

    $scope.isRepeatOn = false;
    $scope.isShuffleOn = false;
    $scope.isPlaying = false;
	
	
    $scope.play = function() {
        PlayerService.play();

    };

    $scope.pause = function() {
        PlayerService.pause();
    };

    $scope.nextTrack = function() {
        PlayerService.nextTrack();
    };

    $scope.previousTrack = function() {
        PlayerService.previousTrack();
    };


    $scope.toggleRepeat = function() {
        PlayerService.setRepeat(!$scope.isRepeatOn);
    };

    $scope.toggleShuffle = function() {
        PlayerService.setShuffle(!$scope.isShuffleOn);
    };

    $scope.$on('$destroy',
        PlayerService.subscribePlayerState(function (state) {
             $scope.isRepeatOn = state.is_repeat_on;
	    $scope.isShuffleOn = state.is_shuffle_on;
	    $scope.isPlaying = state.is_playing;
        })
    );

    $scope.$on('$destroy',
        PlayerService.subscribeCurrentTrackPlaying(function (current_track) {
            $scope.trackProgress = 0;
            $scope.trackLength = current_track != null ? Math.floor(current_track.duration / 1000) : 0;
        })
    );

    $scope.$on('$destroy',
        PlayerService.subscribePlaybackProgress(function (trackProgress) {
            if (!isSliding) {
                // dont update progress when user is sliding
                $scope.trackProgress = trackProgress;
            }

        })
    );

    $scope.$on('$destroy',
        PlayerService.subscribeError(function (error) {
            AlertService.error('Player error: ' + error);


        })
    );






	
});



adminControllers.controller('NowPlayingCtrl', function ($scope, PlayerService, CoverService) {

    $scope.hasData = false;


    $scope.$on('$destroy',
        PlayerService.subscribeCurrentTrackPlaying(function (current_track) {
             $scope.hasData = current_track != null;
             $scope.trackName = current_track != null ? current_track.name : '';
	    $scope.artists = current_track != null ? current_track.artists : '';
	    $scope.coverUrl = CoverService.createCoverUrlProxy(current_track != null ? current_track.link : null);

        })
    );

		
});


adminControllers.controller('PlaylistCtrl', function ($scope, $rootScope, SpotifyService) {

	
    SpotifyService.getPlaylists(function (playlists) {
        $scope.grid = new GridHelper(4, playlists);
    });


    $scope.showPlaylistInfo = function (link) {
        $rootScope.$emit('show-playlist-info', link);
    };
	

});




adminControllers.controller('PlaylistInfoCtrl', function ($scope, $rootScope, $element, SpotifyService, PlayerService) {

    $element.on('hide.bs.modal', function (e) {
        $scope.$broadcast('container-hidden');
    });

    $scope.player = new TrackCollectionPlayer(PlayerService);
    $scope.$on('$destroy', $scope.player.destroy);
	
    $scope.$on('$destroy',
        $rootScope.$on('show-playlist-info', function(e, link) {

            SpotifyService.getPlaylistInfo(link, function (playlist) {

                $scope.playlist = playlist;

                $scope.player.refresh();

                $element.modal('show');

            });

            $rootScope.$emit('init-rfid-status', link);

        }));

		
});


adminControllers.controller('TrackInfoCtrl', function ($scope, $rootScope, $element, SpotifyService) {

    $element.on('hide.bs.modal', function (e) {
        $scope.$broadcast('container-hidden');
    });

	
    $scope.$on('$destroy',
        $rootScope.$on('show-track-info', function(e, link) {

            SpotifyService.getTrackInfo(link, function (track) {

                $scope.track = track;
                $element.modal('show');
            });

            $rootScope.$emit('init-rfid-status', link);
        }));

		
});


adminControllers.controller('PlayQueueCtrl', function ($scope, $rootScope, SpotifyService, PlayerService) {

    function updatePlayQueue()
    {
        SpotifyService.getPlayQueue(function (tracks) {
            $scope.tracks = tracks;
        });
    }

    $scope.player = new TrackCollectionPlayer(PlayerService);
    $scope.$on('$destroy', $scope.player.destroy);

    $scope.$on('$destroy', PlayerService.subscribePlayQueueChanged(updatePlayQueue));

    updatePlayQueue();
		
});


adminControllers.controller('RFIDTagsCtrl', function ($scope, RFIDTagService, PlayerService) {
    var albumTags = [];
    var playlistTags = [];
    var trackTags = [];
    $scope.tags = {
        album: {
            caption: 'Albums',
            grid: new GridHelper(4, albumTags)
        },
        playlist: {
            caption: 'Playlists',
            grid: new GridHelper(4, playlistTags)
        },
        track: {
            caption: 'Tracks',
            grid: new GridHelper(4, trackTags)
        }
    };

    RFIDTagService.getAll(function (tags) {
        for (var i = 0; i < tags.length; i++) {
            var tag = tags[i];

            switch (tag.type)
            {
                case 'playlist': playlistTags.push(tag); break;
                case 'album': albumTags.push(tag); break;
                case 'track': trackTags.push(tag); break;
            }
        }

    });

		
});



adminControllers.controller('DashboardCtrl', function ($scope, $rootScope, SpotifyService, AlertService, RFIDTagService) {

    $scope.spotifyState = null;
    $scope.attachedRfIdReaders = [];
    $scope.credentialsStored = false;

    $scope.showSpotifyCredentials = function () {
        $rootScope.$emit('show-spotify-credentials');
    };

    $scope.forgetCredentials = function () {
        SpotifyService.logout(function() {
            AlertService.info('Changes will take affect after reboot');
        });
    };

    // subscribe for credentials stored status
    $scope.$on('$destroy',
        SpotifyService.subscribeCredentialsStored(function (is_stored) {
            $scope.credentialsStored = is_stored;
        })
    );

    // subscribe for rfid reader status
    $scope.$on('$destroy',
        RFIDTagService.subscribeAttachedReaders(function (readers) {
            $scope.attachedRfIdReaders = readers;
        })
    );

    // subscribe for spotify login state
    $scope.$on('$destroy',
        SpotifyService.subscribeLoginState(function (state) {
            $scope.spotifyState = state;
        })
    );
		
});


adminControllers.controller('SpotifyCredentialsCtrl', function ($scope, $rootScope, $element, SpotifyService) {



    $scope.$on('$destroy',
        $rootScope.$on('show-spotify-credentials', function(e) {
            $scope.errorAlert = null;
            $element.modal('show');

        }));

    $scope.login = function (username, password) {
        SpotifyService.login(username, password, function (result) {
            $scope.errorAlert = result.error;
            if (!result.error) {
                $element.modal('hide');
            }

        });
    };
		
});
