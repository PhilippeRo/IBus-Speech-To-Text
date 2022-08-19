# vim:set et sts=4 sw=4:
#
# ibus-stt - Speech To Text engine for IBus
# Copyright (C) 2022 Philippe Rouquier <bonfire-app@wanadoo.fr>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import weakref

from gi.repository import GObject
from gi.repository import Gio

from sttutils import *

from sttgstvosk import STTGstVosk

LOG_MSG=logging.getLogger()

class STTGstFactory(GObject.GObject):
    __gtype_name__ = "STTGstFactory"

    def __init__(self):
        super().__init__()

        self._current_engine=None
        self._preload=None

        self.__settings=Gio.Settings.new("org.freedesktop.ibus.engine.stt")
        self.__settings.connect("changed::preload", self.__preload_changed)
        self.__update_preloaded_engine()

    def new_engine(self):
        engine=None if self._current_engine is None else self._current_engine()
        if engine is None:
            LOG_MSG.debug("new engine")
            engine=STTGstVosk()
            self._current_engine=weakref.ref(engine)
        else:
            engine.hold()

        return engine

    def __update_preloaded_engine(self):
        preload=self.__settings.get_boolean("preload")
        if preload == (self._preload is not None):
            return

        if preload is True:
            # This adds a reference if it exists
            self._preload=self.new_engine()

            LOG_MSG.info("preloading engine")
            self._preload.preload()
        else:
            LOG_MSG.info("unloading engine")
            self._preload.release()
            self._preload=None

    def __preload_changed(self, settings, key):
        self.__update_preloaded_engine()

_GLOBAL_FACTORY = None

def stt_gst_factory_default() :
    global _GLOBAL_FACTORY

    if _GLOBAL_FACTORY == None:
        _GLOBAL_FACTORY = STTGstFactory()

    return _GLOBAL_FACTORY
