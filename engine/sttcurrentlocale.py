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
import locale
import logging

from pathlib import Path

from gi.repository import Gio, GObject

from sttutils import stt_utils_get_local_config_path, stt_utils_get_system_data_path

LOG_MSG=logging.getLogger()

def stt_current_locale_helper_get_override_path(locale_str):
    return str(Path(stt_utils_get_local_config_path(), "overrides-" + locale_str + ".json"))

class STTCurrentLocale(GObject.Object):
    __gtype_name__="STTCurrentLocale"

    __gsignals__= {
        "override-file-changed": (GObject.SIGNAL_RUN_FIRST, None, (bool,)),
        "changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()

        self._locale=""
        self._formatting_file_path=""

        self._settings=Gio.Settings.new("org.freedesktop.ibus.engine.stt")
        self._locale_changed_id=self._settings.connect("changed::locale", self._locale_changed)
        self._locale_paths_changed_id=self._settings.connect("changed::locale-paths", self._locale_paths_changed)

        self._monitor = None

        locale_str=self._settings.get_string("locale")
        locale_str=self._check_default_locale(locale_str)
        self._set_locale(locale_str)

    def _override_changed(self, monitor, file, other_file, event_type):
        if event_type not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, \
                              Gio.FileMonitorEvent.DELETED):
            return

        self.emit("override-file-changed", bool(event_type == Gio.FileMonitorEvent.DELETED))

    def _set_formatting_file_path(self, path):
        if path == self._formatting_file_path:
            return

        LOG_MSG.debug("updating formatting file path (%s)", path)

        self._formatting_file_path=path
        self.emit("changed")

    def _get_formatting_file_from_settings(self):
        paths_json_string = self._settings.get_string("locale-paths")
        if paths_json_string in (None,"None",""):
            return None

        paths_dict=json.loads(paths_json_string)
        return paths_dict.get(self._locale, None)

    def _get_formatting_file(self):
        path=self._get_formatting_file_from_settings()
        return path

    def _locale_paths_changed(self, settings, key):
        LOG_MSG.debug("settings formatting file paths changed")
        path=self._get_formatting_file()
        self._set_formatting_file_path(path)

    def _load_json_file(self, json_path):
        LOG_MSG.debug("loading JSON file (%s)", str(json_path))
        if not json_path.is_file():
            LOG_MSG.info("wrong or missing filename (%s)", str(json_path))
            return None

        with json_path.open() as json_file:
            try:
                # Catch ill-formatted files
                json_data = json.load(json_file)
                if json_data in [None, {}]:
                    LOG_MSG.debug("empty file (%s)", str(json_path))

            except json.JSONDecodeError:
                LOG_MSG.warning("the JSON format of the file is wrong (%s)", str(json_data))
                return None

        return json_data

    @property
    def formatting(self):
        if self._formatting_file_path not in [None,""]:
            json_path=Path(self._formatting_file_path)
            return self._load_json_file(json_path)

        json_path=Path(stt_utils_get_system_data_path(), "formatting", self._locale + ".json")
        json_data=self._load_json_file(json_path)
        if json_data is not None:
            return json_data

        if len(self._locale) <= 2:
            return None

        json_path=Path(stt_utils_get_system_data_path(), "formatting", self._locale[:2] + ".json")
        return self._load_json_file(json_path)

    def formatting_file_path(self, formatting_file_path):
        LOG_MSG.debug("set formatting file path from %s to %s",
                      self._formatting_file_path, formatting_file_path)

        paths_json_string = self._settings.get_string("locale-paths")
        if paths_json_string in (None,"None",""):
            paths_dict={}
        else:
            paths_dict=json.loads(paths_json_string)

        paths_dict[self._locale]=formatting_file_path
        paths_json_string=json.dumps(paths_dict)

        self._settings.disconnect(self._locale_paths_changed_id)
        self._settings.set_string("locale-paths", paths_json_string)
        self._locale_paths_changed_id=self._settings.connect("changed::locale-paths", self._locale_paths_changed)

        self._set_formatting_file_path(formatting_file_path)

    def _default_overriding_file_path(self):
        return Path(stt_utils_get_local_config_path(), "overrides-" + self._locale + ".json")

    @property
    def overriding(self):
        # Note: there is no defaulting to locale prefix if locale does not exist
        json_path=self._default_overriding_file_path()
        return self._load_json_file(json_path)

    @overriding.setter
    def overriding(self, json_data):
        json_path=self._default_overriding_file_path()

        # Ensure the path to our directory has been created
        json_path.parent.mkdir(parents=True, exist_ok=True)

        with json_path.open("w") as json_file:
            json.dump(json_data, json_file)

    def _set_locale(self, locale_str):
        LOG_MSG.debug("setting object locale (from %s to %s)", self._locale, locale_str)
        if locale_str != self._locale:
            self._locale = locale_str
            self._formatting_file_path=""

            # Monitor the override file for any change
            override_file_path=self._default_overriding_file_path()
            self._monitor=Gio.File.new_for_path(str(override_file_path)).monitor(Gio.FileMonitorFlags.NONE, None)
            self._monitor.connect("changed", self._override_changed)

            # Find path of formatting file (if any) and try to load
            path=self._get_formatting_file()

            # The following function emits "changed" signal, no need to do it
            self._set_formatting_file_path(path)
        else:
            # Even if the locale is the same, if we reached this point,
            # default_locale will have changed since we checked before with
            # _check_default_locale().
            self.emit("changed")

    def _check_default_locale(self, locale_str):
        if locale_str in (None,"","None"):
            # Nothing is set, use default for current system locale
            locale_str=locale.getlocale()[0]
            self.default_locale=True
            LOG_MSG.info("locale is system default (%s)", locale_str)
        else:
            self.default_locale=False
            LOG_MSG.info("locale is %s (not system default)", locale_str)
        return locale_str

    def _check_locale_change(self, locale_str):
        # if it is the default locale and locale_str == None, no need
        if self.default_locale == True and locale_str in [None, "None"]:
            LOG_MSG.debug("no change - setting default locale (None)")
            return False

        if self.default_locale == False and locale_str == self.locale:
            LOG_MSG.debug("setting same locale (%s)", locale_str)
            return False

        return True

    def _locale_changed(self, settings, key):
        locale_str = settings.get_string("locale")
        LOG_MSG.debug("locale setting changed from %s to %s (default locale = %s)",
                      self.locale, locale_str, self.default_locale)

        if self._check_locale_change(locale_str) == False:
            return

        locale_str = self._check_default_locale(locale_str)
        self._set_locale(locale_str)

    @property
    def locale(self):
        return self._locale

    @locale.setter
    def locale(self, locale_str):
        LOG_MSG.debug("set locale name from %s to %s (default locale = %s)",
                      self.locale, locale_str, self.default_locale)

        if self._check_locale_change(locale_str) == False:
            return

        self._settings.disconnect(self._locale_changed_id)
        self._settings.set_string("locale", locale_str)
        self._locale_changed_id=self._settings.connect("changed::locale", self._locale_changed)

        locale_str = self._check_default_locale(locale_str)
        self._set_locale(locale_str)


_CURRENT_LOCALE = None

def stt_current_locale() :
    global _CURRENT_LOCALE

    if _CURRENT_LOCALE == None:
        _CURRENT_LOCALE = STTCurrentLocale()

    return _CURRENT_LOCALE
