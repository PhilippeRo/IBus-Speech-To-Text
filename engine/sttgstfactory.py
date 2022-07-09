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

from gi.repository import GObject
from gi.repository import Gio

from sttutils import *

from sttgstvosk import STTGstVosk
from sttgsthandler import STTGstHandler

LOG_MSG=logging.getLogger()

class STTGstFactory(GObject.GObject):
    __gtype_name__ = "STTGstFactory"

    def __init__(self):
        super().__init__()

        self._preload=False
        self._current_engine=None
        self._handlers=[]

        self.__settings=Gio.Settings.new("org.freedesktop.ibus.engine.stt")
        self.__settings.connect("changed::preload", self.__preload_changed)
        self.__update_preloaded_engine()

    def __new_engine(self):
        engine=STTGstVosk()
        return engine

    # This could be useful one day if we implement support for different engines
    # def __engine_changed(self):
    #    if self._current_engine == None:
    #        return
    #    # Set the new pipeline in the proper state
    #    new_pipeline=self.__new_engine()
    #    if self._current_engine.is_running():
    #        new_pipeline.run()
    #    elif self._current_engine.is_loaded() == True:
    #        new_pipeline.preload()
    #    self._current_engine=new_pipeline
    #    for handler in self._handlers:
    #        handler.set_pipeline(new_pipeline)

    def __update_preloaded_engine(self):
        self._preload=self.__settings.get_boolean("preload")
        if self._preload == True:
            #Make sure there is not any engine already in use
            if self._current_engine == None:
                self._current_engine=self.__new_engine()

            LOG_MSG.info("preloading Engine")

            self._current_engine.preload()
        elif self._current_engine != None:
            LOG_MSG.info("stopping preload (number of handlers=%i)", len(self._handlers))
            if len(self._handlers) == 0:
                self._current_engine.destroy()
                self._current_engine = None

    def __preload_changed(self, settings, key):
        self.__update_preloaded_engine()

    def __handler_destroy(self, handler):
        handler.stop()

        self._handlers.remove(handler)
        handler.disconnect_by_func(self.__handler_destroy)

        if self._preload == True:
            LOG_MSG.info("no more need for current engine, keeping around because of preload (setting to PAUSED)")
            return

        if len(self._handlers) != 0:
            LOG_MSG.info("keeping current engine around because there is still a handler")
            return

        LOG_MSG.info("no more need for current engine, destroying")
        self._current_engine.destroy()
        self._current_engine=None

    # Note: the caller must call destroy() when this object is no longer needed
    def new_handler(self):
        if self._current_engine == None:
            self._current_engine=self.__new_engine()

        handler=STTGstHandler()
        handler.connect("destroy", self.__handler_destroy)
        handler.set_pipeline(self._current_engine)
        self._handlers.append(handler)
        return handler

_GLOBAL_FACTORY = None

def stt_gst_factory_default() :
    global _GLOBAL_FACTORY

    if _GLOBAL_FACTORY == None:
        _GLOBAL_FACTORY = STTGstFactory()

    return _GLOBAL_FACTORY
