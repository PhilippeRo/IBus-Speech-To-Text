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

from enum import Enum

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gst

LOG_MSG=logging.getLogger()

class STTEngineState(Enum):
    UNKNOWN = 0
    READY = 1
    LOADED = 2
    RUNNING = 3

class STTGstBase (GObject.Object):
    __gtype_name__='STTGstBase'

    __gsignals__ = {
        'result': (GObject.SIGNAL_RUN_FIRST, None, (str, object,)),
        'model-changed': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'state-changed': (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, pipeline_definition):
        super().__init__()
        self._pipeline = Gst.parse_launch(pipeline_definition)
        if self._pipeline is None:
            LOG_MSG.error("no pipeline")

        self._buffer_id = 0 # GLib.timeout_add(100, self._print_buffer)

        self._bus = self._pipeline.get_bus()
        self._bus.add_signal_watch_full(GLib.PRIORITY_LOW)
        self._bus_error_id = self._bus.connect("message::error", self._handle_error_message)
        self._bus_warning_id = self._bus.connect("message::warning", self._handle_warning_message)
        self._bus_state_changed_id = self.bus.connect("message::state-changed", self._handle_state_changed_message)

        self._target=STTEngineState.UNKNOWN

    def __del__(self):
        LOG_MSG.info("GstBase __Del__")

    def destroy (self):
        if self._buffer_id:
            GLib.source_remove(self._buffer_id)
            self._buffer_id=0

        self._bus.disconnect(self._bus_error_id)
        self._bus.disconnect(self._bus_warning_id)
        self._bus.disconnect(self._bus_state_changed_id)
        self._bus_error_id = 0
        self._bus_warning_id = 0
        self._bus_state_changed_id = 0

        self._bus.remove_signal_watch()
        self._bus=None

        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline=None

        LOG_MSG.info("GstBase.destroy() called")

    @property
    def pipeline(self):
        return self._pipeline

    @property
    def bus(self):
        return self._bus

    def _handle_error_message (self, bus, message):
        error, debug = message.parse_error()
        LOG_MSG.error("message (%s), %s", error.message, debug)

    def _handle_warning_message (self, bus, message):
        warning, debug = message.parse_warning()
        LOG_MSG.warning("message (%s), %s", warning.message, debug)

    def _handle_state_changed_message (self, bus, message):
        (old_state, new_state, pending) = message.parse_state_changed ()
        LOG_MSG.debug("state changed from %s to %s (%s)", old_state, new_state, message.src)

        # The signal can trigger some functions that are time consuming,
        # especially if they are called several times in a short while.
        # So, only emit the signal if the state is paused or playing and if the
        # whole pipeline's state changed.
        if new_state in [Gst.State.PAUSED, Gst.State.PLAYING] and \
           message.src == self._pipeline:
            self.emit("state-changed")

    def __get_state(self, strict):
        if self._pipeline is None:
            LOG_MSG.error('no pipeline')
            return STTEngineState.UNKNOWN

        ret, state, pending = self._pipeline.get_state (0)
        if ret == Gst.StateChangeReturn.FAILURE:
            LOG_MSG.info("pipeline get_state failure")
            return STTEngineState.UNKNOWN

        if ret == Gst.StateChangeReturn.ASYNC:
            if strict == True:
                LOG_MSG.debug("impending pipeline state change")
                return STTEngineState.UNKNOWN

            if pending == Gst.State.PLAYING:
                return STTEngineState.RUNNING

            if pending == Gst.State.PAUSED:
                return STTEngineState.LOADED

        if state == Gst.State.PLAYING:
            return STTEngineState.RUNNING

        if state == Gst.State.PAUSED:
            return STTEngineState.LOADED

        return STTEngineState.READY

    def is_running (self):
        if self.has_model() == False:
            return False

        return bool(self.__get_state(False) == STTEngineState.RUNNING)

    def is_loaded (self):
        return bool(self.__get_state(False) == STTEngineState.LOADED)

    def preload (self):
        if self._pipeline == None:
            LOG_MSG.error('no pipeline')
            return False

        # Only preload if not playing or not moving toward playing state
        self._target=STTEngineState.LOADED
        if self.__get_state(False) != STTEngineState.READY:
            LOG_MSG.debug("pipeline not in ready state")
            return True

        ret = self._pipeline.set_state (Gst.State.PAUSED)
        LOG_MSG.debug("preloading pipeline %i", ret)

        if ret == Gst.StateChangeReturn.FAILURE:
            LOG_MSG.error("failed to preload pipeline")
            return False

        # Note: we might not be ready yet if vosk is loading model.
        # In this case, wait for message ASYNC_DONE
        return True

    def _run_real(self):
        self._pipeline.call_async(Gst.Element.set_state, Gst.State.PLAYING)

        # Note: we might not be ready yet if vosk is loading model.
        # In this case, wait for message ASYNC_DONE
        return True

    def run (self):
        if self._pipeline == None:
            LOG_MSG.error('no pipeline')
            return False

        self._target=STTEngineState.RUNNING
        return self._run_real()

    def _stop_real(self):
        ret = self._pipeline.set_state (Gst.State.PAUSED)
        LOG_MSG.info("stopping pipeline")
        if ret == Gst.StateChangeReturn.FAILURE:
            LOG_MSG.error("no way to set to PAUSED")
            return False

        # Get final results
        self.get_final_results()

        self._pipeline.send_event(Gst.Event.new_flush_start())
        self._pipeline.send_event(Gst.Event.new_flush_stop(True))
        return True

    def stop (self):
        if self._pipeline == None:
            LOG_MSG.error("no pipeline")
            return False

        # Only stop if playing or moving toward playing state
        if self.__get_state(False) != STTEngineState.RUNNING:
            LOG_MSG.info("pipeline not running")
            return True

        self._target=STTEngineState.LOADED
        return self._stop_real()

    def get_final_results(self):
        LOG_MSG.info("get final results not implemented for this backend")
        return False

    def has_model(self):
        return bool(self._pipeline != None)

    def do_model_changed(self):
        if self.has_model() == False:
            if self._target == STTEngineState.RUNNING:
                LOG_MSG.debug("model changed, adjusting state to target (PAUSED)")
                self._stop_real()
        else:
            if self._target == STTEngineState.RUNNING:
                LOG_MSG.debug("model changed, adjusting state to target (RUNNING)")
                self._run_real()

    def _print_buffer(self):
        print("Buffer level is",
              self._pipeline.get_by_name("Buffer").get_property("current-level-time")/1000000000.0,
              self._pipeline.get_by_name("Buffer").get_property("current-level-bytes"),
              self._pipeline.get_by_name("Buffer").get_property("current-level-buffers"))

        return True
