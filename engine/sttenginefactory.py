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

import gi

gi.require_version('IBus', '1.0')
from gi.repository import IBus

from sttengine import STTEngine

LOG_MSG=logging.getLogger()

class STTEngineFactory(IBus.Factory):
    __gtype_name__ = 'STTEngineFactory'

    def __init__(self, bus):
        self._bus=bus
        self._current_engine=None
        super().__init__(object_path=IBus.PATH_FACTORY,
                         connection=bus.get_connection())
        # Stop there, we create this object to control engine creation

    def do_create_engine(self, engine_name):
        LOG_MSG.debug("New engine requested %s", engine_name)
        if engine_name != "stt":
            return super().do_create_engine(engine_name)

        engine=STTEngine(self._bus, "/org/freedesktop/IBus/STT")
        self._current_engine=engine
        LOG_MSG.debug("Creating new engine")
        return engine

    def do_destroy(self):
        self._current_engine=None
        super().do_destroy(self)