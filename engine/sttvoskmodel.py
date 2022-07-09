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

from pathlib import Path

from gi.repository import GObject, Gio

from sttvoskmodelmanagers import stt_vosk_local_model_manager

LOG_MSG=logging.getLogger()

class STTVoskModel(GObject.Object):
    __gtype_name__="STTVoskModel"

    __gsignals__={
        "changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, locale_str=None):
        super().__init__()

        self._locale_str=locale_str

        self._settings=Gio.Settings.new("org.freedesktop.ibus.engine.stt")
        self._settings_id=self._settings.connect("changed::vosk-models", self._models_changed)

        self._model_name=None
        self._model_path=None
        self._valid_model=False

        model=self._get_model_from_settings()
        self._set_model(model)

        self._model_path_added_id = stt_vosk_local_model_manager().connect("added", self._model_added_cb)
        self._model_path_removed_id = stt_vosk_local_model_manager().connect("removed", self._model_removed_cb)

    def __del__(self):
        stt_vosk_local_model_manager().disconnect(self._model_path_added_id)
        stt_vosk_local_model_manager().disconnect(self._model_path_removed_id)
        if self._model_name is None and self._model_path is not None:
            stt_vosk_local_model_manager().unregister_custom_model_path(self._model_path)

    def _get_model_from_settings(self):
        models_json_string = self._settings.get_string("vosk-models")
        if models_json_string in (None,"None",""):
            return None

        models_dict=json.loads(models_json_string)
        return models_dict.get(self._locale_str, None)

    def _set_model(self, model):
        LOG_MSG.debug("new model (%s, current path=%s / current name=%s)", model, self._model_path, self._model_name)
        if model == None:
            if self._model_name == None and self._model_path == None:
                return

            self._model_name=None
            self._mode_path=None
            self._valid_model=False

            self.emit("changed")
            return

        model=model.rstrip("/")

        model_name=self._model_name
        model_path=self._model_path

        # See if it is a name or a custom path (and then it's absolute)
        if Path(model).is_absolute() == True:
            if self._model_name is None and self._model_path == model:
                return

            self._model_name=None
            self._model_path=model
            stt_vosk_local_model_manager().register_custom_model_path(model, self._locale_str)
            self._valid_model=stt_vosk_local_model_manager().path_available(model)
        else:
            # Check if there is not a better path that came up for this model
            tmp_model_path=stt_vosk_local_model_manager().get_best_path_for_model(model)
            if self._model_name == model and tmp_model_path == model_path:
                return

            self._model_name=model
            self._model_path=tmp_model_path
            self._valid_model=bool(tmp_model_path is not None)

        if model_path not in [self._model_path, None] and model_name is None:
            stt_vosk_local_model_manager().unregister_custom_model_path(model_path)

        LOG_MSG.debug("model changed (valid=%i, current path=%s - current name=%s)", self._valid_model, self._model_path, self._model_name)
        self.emit("changed")

    def _models_changed(self, settings, key):
        model=self._get_model_from_settings()
        self._set_model(model)

    def _model_added_cb(self, manager, name, path):
        if self._model_name is not None:
            if name != self._model_name:
                return

            # A new path for our model has just appeared. It can' be the
            # current one. See if our path is still the best.
            model_path=stt_vosk_local_model_manager().get_best_path_for_model(name)
            if self._model_path == model_path:
                return

            self._model_path=model_path
        elif self._model_path != path:
            return

        self._valid_model = True
        self.emit("changed")

    def _model_removed_cb(self, manager, name, path):
        if self._model_name is not None:
            if name != self._model_name:
                return

            # A path for the current model was removed; it's not the one we use.
            if self._model_path != path:
                return

            # The path for our model was removed; there might be others
            self._model_path=stt_vosk_local_model_manager().get_best_path_for_model(name)
            self._valid_model=bool(self._model_path is not None)
        elif self._model_path == path:
            self._valid_model=False
        else:
            return

        self.emit("changed")

    def available(self):
        return self._valid_model

    def get_locale(self):
        return self._locale_str

    def get_name(self):
        return self._model_name

    def get_path(self):
        return self._model_path

    def set_name(self, model_name):
        self._set_model(model_name)

        models_json_string = self._settings.get_string("vosk-models")
        if models_json_string in (None,"None",""):
            models_dict={}
        else:
            models_dict=json.loads(models_json_string)

        models_dict[self._locale_str]=model_name
        models_json_string=json.dumps(models_dict)

        self._settings.disconnect(self._settings_id)
        self._settings.set_string("vosk-models", models_json_string)
        self._settings_id=self._settings.connect("changed::vosk-models", self._models_changed)
