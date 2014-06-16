#
# Copyright 2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
"""
    Implementation for Trackable, a wrapper for objects whose values should be
    trackable for changes
"""

import collections
import threading


class ChangeCounter(object):
    def __init__(self):
        self._counter_lock = threading.Lock()
        self._current = 0

    def next(self):
        with self._counter_lock:
            self._current += 1
            return self._current

    def current(self):
        with self._counter_lock:
            return self._current


_counter = ChangeCounter()


def counter():
    return _counter


class Trackable(object):
    """
        Trackable implements common functionality of TrackableMapping and
        TrackableSequence and it is not required to be used.
    """
    def __init__(self):
        super(Trackable, self).__init__()
        self._last_changed = counter().next()
        self._item_last_changed = {}
        self._tracked = None
        self._watcher = None
        self._track_depth = 0

    def _merge(self, value):
        raise NotImplementedError("Missing implementation of _merge")

    def _set_item(self, key, value):
        needs_update = True
        if key in self._tracked:
            old = self._tracked[key]
            if isinstance(old, Trackable):
                old._merge(value)
                # if an item is updated through _merge it does not need to be
                # updated because and we are not propagating the update, this
                # would bubble up on it's own throw the setters
                needs_update = False
            elif old == value:
                    # Not updated, no change required
                    needs_update = False
            else:
                self._tracked.__setitem__(key, _wrap(value, self,
                                                     self._track_depth))
        else:
            self._tracked.__setitem__(key, _wrap(value, self,
                                                 self._track_depth))
        if needs_update:
            self._on_item_changed(key)

    def _on_item_removed(self, key):
            changed = counter().next()
            self._last_changed = changed
            del self._item_last_changed[key]
            if self._watcher:
                self._on_subitem_changed(changed)

    def _on_item_changed(self, key):
        changed = counter().next()
        self._last_changed = changed
        self._item_last_changed[key] = changed
        if self._watcher:
            self._on_subitem_changed(changed)

    def _on_subitem_changed(self, changed):
        self._last_changed = changed
        if self._watcher:
            self._watcher._on_subitem_changed(changed)

    def changed(self, since, key=None):
        if not key:
            return self._last_changed > since
        if isinstance(self._tracked.get(key, None), Trackable):
            return self._tracked[key].changed(since=since)
        return self._item_last_changed[key] > since

    @property
    def last_changed(self):
        return self._last_changed


def _wrap(v, watcher, track_depth):
    if track_depth <= 0 or isinstance(v, Trackable):
        return v
    elif isinstance(v, collections.MutableSequence):
        return TrackableSequence(tracked=v, _watcher=watcher,
                                 track_depth=track_depth - 1)
    elif isinstance(v, collections.MutableMapping):
        return TrackableMapping(tracked=v, _watcher=watcher,
                                track_depth=track_depth - 1)
    return v


class TrackableSequence(collections.MutableSequence, Trackable):
    """
        TrackableSequence implements a mutable sequence interface to
        track changes to the elements in the list.
    """
    def __init__(self, tracked=None, track_depth=0, _watcher=None):
        super(TrackableSequence, self).__init__()
        self._tracked = tracked.__class__() if tracked else []
        self._track_depth = track_depth
        self._watcher = _watcher
        if tracked:
            for elem in tracked:
                self.append(elem)

    def insert(self, index, value):
        self._tracked.insert(index, _wrap(value, self, self._track_depth))
        self._on_item_changed(index)

    def _merge(self, value):
        # lists when different need a full update
        if self._tracked != value:
            self._item_last_changed = {}
            self._tracked = self._tracked.__class__()
            for elem in value:
                self.append(elem)

    def __setitem__(self, key, value):
        self._set_item(key, value)

    def __getitem__(self, key):
        return self._tracked.__getitem__(key)

    def __delitem__(self, idx):
        self._tracked.__delitem__(idx)
        if not isinstance(self._tracked, Trackable):
            self._on_item_removed(idx)

    def __len__(self):
        return self._tracked.__len__()

    def __iter__(self):
        return self._tracked.__iter__()

    def __hash__(self):
        return self._tracked.__hash__()


class TrackableMapping(Trackable, collections.MutableMapping):
    """
        TrackableMapping implements a mutable mapping interface to track
        changes in the keys/values in a mapping and acts like a proxy thereof
    """
    def __init__(self, tracked=None, track_depth=0, _watcher=None):
        """
        :param tracked:     The object which should be tracked usually a dict
        :param track_depth: The depth the tracking should be applied
                            the default value is 0 which means only the current
                            objects keys are tracked.
        :return:
        """
        super(TrackableMapping, self).__init__()
        self._tracked = tracked.__class__() if tracked else {}
        self._track_depth = track_depth
        self._watcher = _watcher
        if tracked:
            for k, v in tracked.iteritems():
                self[k] = v

    def update_filtered(self, value, filter_if):
        for k in value.keys():
            if filter_if(k):
                continue
            self[k] = value[k]

    def _merge(self, value):
        for k in self._tracked.keys():
            if k not in value:
                del self[k]
            elif self._tracked[k] != value[k]:
                self[k] = value[k]
        for k in value.keys():
            if k not in self._tracked:
                self[k] = value[k]

    def __setitem__(self, key, value):
        self._set_item(key, value)

    def __getitem__(self, key):
        return self._tracked.__getitem__(key)

    def __delitem__(self, key):
        self._tracked.__delitem__(key)
        if not isinstance(self._tracked, Trackable):
            self._on_item_removed(key)

    def __len__(self):
        return self._tracked.__len__()

    def __iter__(self):
        return self._tracked.__iter__()

    def __hash__(self):
        return self._tracked.__hash__()
