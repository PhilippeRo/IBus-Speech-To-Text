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
from gi.repository import Gst

LOG_MSG=logging.getLogger()

class STTGstHandler(GObject.Object):
    __gtype_name__ = 'STTGstHandler'

    __gsignals__ = {
        'destroy': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'model-changed': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'state': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'text': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        'partial-text': (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        'alternatives': (GObject.SIGNAL_RUN_FIRST, None, (object,))
    }

    def __init__(self):
        super().__init__()

        self._pipeline=None
        self._model_changed_id=0
        self._result_id=0
        self._bus_state_changed_id=0
        self._bus_error_id=0
        self._bus_warning_id=0

    def __del__(self):
        LOG_MSG.info("GstHandler destroyed")

    def set_pipeline(self, pipeline):
        if self._pipeline != None:
            # Note: this will happen one day if we implement different engines.
            # In the meantime, object has only one engine during its lifetime.
            self.__disconnect()

            old_pipeline=self._pipeline
            self._pipeline=pipeline

            if self._pipeline.is_running() != old_pipeline.is_running():
                self.emit("state")
        else:
            self._pipeline=pipeline

        self.__connect()

    def __connect(self):
        self.__disconnect()

        if self._model_changed_id == 0:
            self._model_changed_id=self._pipeline.connect("model-changed", self._model_changed)

        if self._result_id == 0:
            self._result_id=self._pipeline.connect("result", self._got_result)

        if self._bus_state_changed_id != 0:
            return

        self._bus_state_changed_id = self._pipeline.bus.connect("message::state-changed", self.__handle_state_changed_message)
        self._bus_error_id = self._pipeline.bus.connect("message::error", self.__handle_error_message)
        self._bus_warning_id = self._pipeline.bus.connect("message::warning", self.__handle_warning_message)

    def __disconnect(self):
        if self._model_changed_id != 0:
            self._pipeline.disconnect(self._model_changed_id)
            self._model_changed_id = 0

        if self._result_id != 0:
            self._pipeline.disconnect(self._result_id)
            self._result_id = 0

        if self._bus_state_changed_id == 0:
            return

        self._pipeline.bus.disconnect(self._bus_state_changed_id)
        self._pipeline.bus.disconnect(self._bus_error_id)
        self._pipeline.bus.disconnect(self._bus_warning_id)
        self._bus_state_changed_id = 0
        self._bus_error_id = 0
        self._bus_warning_id = 0

    def _got_result(self, pipeline, msg_name, data):
        self.emit(msg_name, data)

    def _model_changed(self, pipeline):
        self.emit("model-changed")

    def __handle_state_changed_message (self, bus, message):
        (old_state, new_state, pending) = message.parse_state_changed ()
        LOG_MSG.debug("state changed from %s to %s (%s)", old_state, new_state, message.src)

        # The signal can trigger some functions that are time consuming,
        # especially if they are called several times in a short while.
        # So, only emit the signal if the state is paused or playing and if the
        # whole pipeline's state changed.
        if new_state in [Gst.State.PAUSED, Gst.State.PLAYING] and \
           message.src == self._pipeline.pipeline:
            self.emit("state")

    def __handle_error_message (self, bus, message):
        error, debug = message.parse_error()
        LOG_MSG.error("message (%s), %s", error.message, debug)

    def __handle_warning_message (self, bus, message):
        warning, debug = message.parse_warning()
        LOG_MSG.warning("message (%s), %s", warning.message, debug)

    def is_running (self):
        if self._pipeline == None:
            LOG_MSG.error('no pipeline')
            return False

        return self._pipeline.is_running()

    def run (self):
        if self._pipeline == None:
            LOG_MSG.error('no pipeline')
            return False

        return self._pipeline.run()

    def stop (self):
        if self._pipeline == None:
            LOG_MSG.error('no pipeline')
            return False

        return self._pipeline.stop()

    def get_final_results (self):
        if self._pipeline == None:
            LOG_MSG.error('no pipeline')
            return False

        return self._pipeline.get_final_results()

    def has_model(self):
        return self._pipeline.has_model()

    def destroy (self):
        # This is needed if we want to drop the python ref count
        self.__disconnect()
        self.emit('destroy')
        self._pipeline = None

    def set_alternatives_num(self, number):
        self._pipeline.set_alternatives_num(number)
