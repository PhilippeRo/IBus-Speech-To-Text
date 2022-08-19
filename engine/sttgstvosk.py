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

import json
import logging

from gi.repository import Gst

from sttutils import *
from sttgstbase import STTGstBase

from sttcurrentlocale import stt_current_locale
from sttvoskmodel import STTVoskModel

LOG_MSG=logging.getLogger()

class STTGstVosk(STTGstBase):
    __gtype_name__ = 'STTGstVosk'

    #"removesilence remove=true minimum-silence-time=3000000000 squash=true silent=false ! " \
    #"removesilence remove=true minimum-silence-time=1000000000 threshold=-40 squash=true silent=false ! " \
    #slave-method=3 /                   "queue max-size-bytes=4294967295 ! " \

    _pipeline_def="pulsesrc blocksize=19200 ! " \
                  "audio/x-raw,format=S16LE,rate=48000,channels=1 ! " \
                  "webrtcdsp noise-suppression-level=3 echo-cancel=false ! " \
                  "queue2 max-size-bytes=4294967294 name=Buffer max-size-time=0 max-size-buffers=0 ! " \
                  "vosk name=VoskMain ! " \
                  "fakesink"

    _pipeline_def_alt="pulsesrc blocksize=19200 ! " \
                      "audio/x-raw,format=S16LE,rate=48000,channels=1 ! " \
                      "queue2 max-size-bytes=4294967294 name=Buffer max-size-time=0 max-size-buffers=0 ! " \
                      "vosk name=VoskMain ! " \
                      "fakesink"

    def __init__(self, current_locale=None):
        plugin=Gst.Registry.get().find_plugin("webrtcdsp")
        if plugin is not None:
            super().__init__(pipeline_definition=STTGstVosk._pipeline_def)
            LOG_MSG.debug("using Webrtcdsp plugin")
        else:
            super().__init__(pipeline_definition=STTGstVosk._pipeline_def_alt)
            LOG_MSG.debug("not using Webrtcdsp plugin")

        if self.pipeline is None:
            LOG_MSG.error("pipeline was not created")
            return

        self._vosk = self.pipeline.get_by_name("VoskMain")
        if self._vosk is None:
            LOG_MSG.error("no Vosk element!")

        self._bus_id = self.bus.connect("message::element", self.__handle_vosk_message)

        if current_locale is None:
            self._current_locale = stt_current_locale()
        else:
            self._current_locale = current_locale

        self._locale_id = self._current_locale.connect("changed", self._locale_changed)

        self._model_id = 0
        self._model = None
        self._set_model()

    def __del__(self):
        LOG_MSG.info("Vosk __del__")
        super().__del__()

    def destroy (self):
        self._current_locale.disconnect(self._locale_id)
        self._locale_id = 0

        if self._model_id != 0:
            self._model.disconnect(self._model_id)
            self._model_id = 0

        self.bus.disconnect(self._bus_id)
        self._bus_id = 0

        self._vosk = None

        LOG_MSG.info("Vosk.destroy() called")
        super().destroy()

    def _set_model_path(self):
        if self._vosk == None:
            return

        current_model_path=self._vosk.get_property ("speech-model")
        if self._model == None or self._model.available() == False:
            LOG_MSG.info("model path does not exist (%s - %s)", self._model.get_name(), self._model.get_path())
            new_model_path=None
        else:
            new_model_path=self._model.get_path()
            LOG_MSG.debug("model ready %s", new_model_path)

        if current_model_path == new_model_path:
            return

        LOG_MSG.debug("new Vosk model %s", new_model_path)
        self._vosk.set_property ("speech-model", new_model_path)

        # Warn of our state change
        self.emit("model-changed")

    def _model_changed(self, model):
        self._set_model_path()

    def _set_model(self):
        # This function can be called by internal function that rely on signals
        # used for a wide range of changes. So check that the locale has
        # actually changed
        if self._model is not None and \
           self._model.get_locale() == self._current_locale.locale:
            return

        if self._model_id != 0:
            self._model.disconnect(self._model_id)
            self._model_id=0

        self._model = STTVoskModel(locale_str=self._current_locale.locale)
        self._model_id = self._model.connect("changed", self._model_changed)
        self._set_model_path()

    def _locale_changed(self, locale):
        self._set_model()

    def _parse_json (self, json_text):
        if json_text in [None,""]:
            LOG_MSG.debug("empty json answer")
            return

        LOG_MSG.debug("JSON string %s", json_text)
        try:
            # Catch ill-formatted files
            json_data = json.loads(json_text)

        except json.JSONDecodeError:
            LOG_MSG.error("the format of the JSON string is not correct")
            return

        partial_text = json_data.get("partial")
        if partial_text != None:
            if partial_text != "":
                self.emit("partial-text", partial_text)
            return

        text = json_data.get("text")
        if text != None:
            if text != "":
                self.emit("text", text)
            return

        json_alternatives = json_data.get("alternatives")
        if json_alternatives != None:
            text_alternatives = []
            for alternative_iter in json_alternatives:
                text = alternative_iter.get("text")
                if text not in [None,""]:
                    # There are sometimes starting white spaces, remove
                    text_alternatives.append(text.lstrip())

            # Apparently this is pythonic to check if list is empty or not
            if text_alternatives:
                self.emit("alternatives", text_alternatives)
        else:
            LOG_MSG.error("unreadable json answer")

    def get_final_results(self):
        # There is no final results when not playing or paused
        self._parse_json(self._vosk.get_property("final-results"))

    def __handle_vosk_message (self, bus, message):
        msg_struct = message.get_structure ()
        struct_name = msg_struct.get_name ()
        if struct_name is None or struct_name != "vosk":
            return

        self._parse_json(msg_struct.get_string ("current-result"))

    def set_alternatives_num(self, num):
        self._vosk.set_property("alternatives", num)

    def has_model(self):
        if self._model == None or self._model.available() == False:
            return False

        return super().has_model()
