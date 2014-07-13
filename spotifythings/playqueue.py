# -*- coding: utf-8 -*-
from random import shuffle
from spotify import Link

class PlayQueueItem(object):

    def __init__(self, track, original_index):
        self.track = track
        self.original_index = original_index

    def __cmp__(self, other):
        if isinstance(other,PlayQueueItem):
            return self.original_index - other.original_index
        return 0

class PlayeQueueManager(object):

    def __init__(self):
        self.is_shuffle_on = False
        self.is_repeat_on = False
        self.current_track_index = -1
        self.play_queue = []

    def __apply_shuffling(self):
        # locate current item by current track index
        current_item = self.play_queue[self.current_track_index] if self.current_track_index != -1 else None

        if self.is_shuffle_on:
            shuffle(self.play_queue)
        else:
            self.play_queue.sort()

        # set current track index to same track as before shuffle/unshuffle
        if current_item:
            self.current_track_index = self.play_queue.index(current_item)


    def __append_play_queue(self, track):
        next_index = len(self.play_queue)
        self.play_queue.append(PlayQueueItem(track, next_index))

    def replace_queue(self, tracks, playing_track_link_uri):

        # clear current playing track
        self.current_track_index = -1

        # clear current queue
        del self.play_queue[:]


        # add new tracks
        for index, track in enumerate(filter(lambda track: track.availability() == 1,  tracks)):
            self.__append_play_queue(track)
            if str(Link.from_track(track)) == playing_track_link_uri:
                self.current_track_index = index

        # shuffle?
        self.__apply_shuffling()


        if self.current_track_index == -1 and len(self.play_queue) > 0:
            self.current_track_index = 0

    def set_shuffle(self, is_on):
        self.is_shuffle_on = is_on
        self.__apply_shuffling()

    def set_repeat(self, is_on):
        self.is_repeat_on = is_on

    def move_next_track(self):
        queue_length = len(self.play_queue)

        if (self.current_track_index + 1) < queue_length:
            self.current_track_index += 1
            return True
        elif self.is_repeat_on and queue_length > 0:
            self.current_track_index = 0
            return True
        else:
            return False

    def move_previous_track(self):
        queue_length = len(self.play_queue)

        if self.current_track_index >= 1:
            self.current_track_index -= 1
            return True
        elif self.is_repeat_on and queue_length > 0:
            self.current_track_index = queue_length -1
            return True
        else:
            return False

    def change_track(self, track_link):
        for index, item in enumerate(self.play_queue):
            if str(Link.from_track(item.track)) == track_link:
                self.current_track_index = index
                return True

        return False

    def get_tracks(self):
        return [item.track for item in self.play_queue]

    def get_current_track(self):
        return self.play_queue[self.current_track_index].track if self.current_track_index != -1 else None



