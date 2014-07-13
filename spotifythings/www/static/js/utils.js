String.prototype.padLeft = function(c, length) {
    var str = this;
    while (str.length < length)
        str = c + str;
    return str;
}


function formatDuration (duration) {
    var totalSeconds = Math.floor(duration);
    var minutes = Math.floor(totalSeconds / 60);
    var seconds = totalSeconds % 60;

    return minutes + ':' + seconds.toString().padLeft('0', 2);
};