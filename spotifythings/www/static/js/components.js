
function TrackCollectionPlayer(PlayerService) {

    var playingTrack = null;
    var focusedTrack = null;
    var isPlaying = false;
    var unbindings = [];

    // internal eventhandlers
    function currentTrackPlayingHandler(current_track) {
        if (current_track != null) {
            playingTrack = current_track.link;
        }
        else {
            playingTrack = null;
        }


    }

    function playerStateHandler(state) {
        isPlaying = state.is_playing;
    };


    // external events
    this.play = function (collectionLink, track) {

        if (playingTrack == track.link) {

            // this is the current playing track, just resume
            PlayerService.play();

        }
        else {
            PlayerService.playTrack(collectionLink, track.link);
        }

    };

    this.pause = function () {
        PlayerService.pause();
    };

    this.trackFocused = function (track) {
        focusedTrack = track.link;
    };

    this.trackUnFocused = function (track) {
        focusedTrack = null;
    };

    this.displayPlayButton = function (track) {
        return track.link == focusedTrack  && track.is_available && (track.link != playingTrack || !isPlaying);
    };

    this.displayPauseButton = function (track) {
        return track.link == focusedTrack && track.link == playingTrack && isPlaying;
    };

    this.displayLoudspeaker = function (track) {
        return track.link != focusedTrack && track.link == playingTrack;
    };

    this.refresh = function () {
        PlayerService.updateCurrentTrackPlaying(currentTrackPlayingHandler);
        PlayerService.updatePlayerState(playerStateHandler);
    };

    this.destroy = function () {
        for (i = 0; i < unbindings.length; i++) {
            unbindings[i]();
        }
    };

    // subscribe to player events
    unbindings.push(PlayerService.subscribeCurrentTrackPlaying(currentTrackPlayingHandler));
    unbindings.push(PlayerService.subscribePlayerState(playerStateHandler));

}

function GridHelper(itemsPerRow, data) {

    this.getRowCount = function () {		
        return data.length / itemsPerRow;		
    };
	
    this.getItemsForRow = function (rowIndex) {
        var startIndex = rowIndex * itemsPerRow;
        var endIndex = Math.min(data.length, startIndex + itemsPerRow);

        var result = [];
		
        for (var i = startIndex; i < endIndex; i++)
            result.push(data[i]);
			
        return result;
		
    };
}