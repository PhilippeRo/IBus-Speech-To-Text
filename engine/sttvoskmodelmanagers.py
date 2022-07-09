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

import os
import json
import logging
from re import search
from pathlib import Path
import urllib.request
from enum import IntEnum
import tempfile
import shutil
import uuid
import threading

from gi.repository import GObject, Gio, GLib

LOG_MSG=logging.getLogger()

# This is from vosk python library. We try to stick to it.
# vosk-api/python/vosk/__init__.py (github).ur
# The preferred directory in which to download models is the first one.
MODEL_DIRS = [os.getenv('VOSK_MODEL_PATH'), Path('/usr/share/vosk'), Path.home() / 'AppData/Local/vosk', Path.home() / '.cache/vosk']
MODEL_PRE_URL = 'https://alphacephei.com/vosk/models/'
MODEL_LIST_URL = MODEL_PRE_URL + 'model-list.json'

DOWNLOADED_MODEL_SUFFIX = ".downloaded_model_tmp"

def _helper_locale_normalize(locale_str):
    lang=locale_str[0:2].lower()
    if len(locale_str) < 5:
        return lang

    lang2=locale_str[3:5]
    return lang+"_"+lang2.upper()

class STTDownloadState(IntEnum):
    STOPPED = -1.0
    UNKNOWN_PROGRESS = -0.5
    UNPACKING = -0.6
    ONGOING = 0.0

class STTVoskModelDescription(GObject.Object):
    __gtype_name__="STTVoskModelDescription"

    def __init__(self, init_model=None):
        super().__init__()
        self.name=init_model.name if init_model is not None else ""
        self.custom=init_model.custom if init_model is not None else False
        self.is_obsolete=init_model.is_obsolete if init_model is not None else False
        self.paths=init_model.name if init_model is not None else []
        self.size=init_model.name if init_model is not None else ""
        self.type=init_model.name if init_model is not None else ""
        self.locale=init_model.name if init_model is not None else ""
        self.url=init_model.name if init_model is not None else ""

        self._operation=None
        self.download_progress=STTDownloadState.STOPPED

    def _download_finished(self):
        # Try not to stop on ongoing operation
        if self._operation.is_cancelled():
            self._operation=None

    def _model_downloaded_thread(self, downloaded_file, destination, status):
        self.download_progress=STTDownloadState.UNPACKING

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Unpack the archive
            LOG_MSG.debug("unpacking model %s in, %s", downloaded_file, tmp_dir)
            shutil.unpack_archive(downloaded_file, tmp_dir, "zip")

            if status.is_cancelled() == True:
                # Note: the directory is set to be deleted on close()
                return

            # Move the contents of the temporary directory to the right place
            model_name=""
            for file in os.listdir(tmp_dir):
                if model_name != "":
                    # This is an error
                    LOG_MSG.error("model is composed of more than one file")
                    break

                model_name=file

            model_src=os.path.join(tmp_dir, model_name)

            # Make sure parent path exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Move the unzipped model directory to directory as a temp file
            copy_id = uuid.uuid4()
            tmp_dst = Path(str(destination) + str(copy_id) + DOWNLOADED_MODEL_SUFFIX)
            LOG_MSG.error("tmp model dest %s", tmp_dst)

            shutil.move(model_src, tmp_dst)

            if status.is_cancelled() == True:
                shutil.rmtree(tmp_dst)

            # Do an atomic rename so that when monitoring triggers a file change
            # we are sure that directory has been properly moved since it's an
            # atomic operation.
            os.rename(tmp_dst, destination)

            if status.is_cancelled() == True:
                shutil.rmtree(destination)

    def _download_model_thread(self, download_link, destination, status):
        with urllib.request.urlopen(download_link) as response:
            length_str = response.getheader('content-length')
            blocksize = 4096
            if length_str:
                length = int(length_str)
                blocksize = max(blocksize, length // 20)
            else:
                length=0

            with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
                size=0
                while True:
                    if status.is_cancelled() == True:
                        # Note: the file is set to be deleted on close()
                        return

                    buffer=response.read(blocksize)
                    if buffer == None or len(buffer) == 0:
                        break

                    tmp_file.write(buffer)
                    size+=len(buffer)
                    if length != 0:
                        self.download_progress=size/length
                    else:
                        self.download_progress=STTDownloadState.UNKNOWN_PROGRESS

                tmp_file.flush()
                self._model_downloaded_thread(tmp_file.name, destination, status)

        self.download_progress=STTDownloadState.STOPPED
        GLib.idle_add(self._download_finished)

    def stop_downloading(self):
        if self._operation is not None:
            # Do not set this to None ourselves.
            # Let the function finish and do it.
            self._operation.cancel()

    def start_downloading(self):
        if self._operation != None:
            return

        LOG_MSG.debug("start downloading model (%s)", self.url)

        self.download_progress=STTDownloadState.ONGOING
        self._operation=Gio.Cancellable()

        download_thread = threading.Thread(target=self._download_model_thread, args=(self.url, Path(MODEL_DIRS[3], self.name), self._operation))
        download_thread.start()

    def get_best_path_for_model(self):
        if self.paths in [None, []]:
            return None

        # First is always the best since we sort them when we add one
        return self.paths[0]

    def delete_paths(self):
        if self.custom == True:
            return

        for path in self.paths:
            # Only remove path in this directory as it is a cache and only if it
            # has a url to download it again. Otherwise let the user deal with
            # it since he installed it in the first place.
            if Path(path).parent == MODEL_DIRS[3] and self.url is not None:
                shutil.rmtree(path)


class STTVoskLocalModelManager(GObject.Object):
    __gtype_name__="STTVoskLocalModelManager"

    __gsignals__={
        # TODO: we might want to change this to use a model instead of a string
        "added": (GObject.SIGNAL_RUN_FIRST, None, (str,str,)),
        "removed": (GObject.SIGNAL_RUN_FIRST, None, (str,str,)),
    }

    def __init__(self):
        super().__init__()
        self._monitors=[]
        self._models_dict={}
        self._locales_dict={}
        self._model_paths_dict={}
        self._get_available_local_models()
        self._custom_paths={}

    def _add_model_description_to_locale(self, model_desc):
        if model_desc.locale is None:
            return

        models_list=self._locales_dict.get(model_desc.locale, None)
        if models_list == None:
            self._locales_dict[model_desc.locale]=[model_desc]
        else:
            models_list.append(model_desc)

    def _new_model_available(self, model_path):
        # Make sure it is not a downloaded model
        if model_path.suffix == DOWNLOADED_MODEL_SUFFIX:
            LOG_MSG.debug("model path is a temporary directory (%s)", model_path)
            return None

        # Make sure it is a directory
        if model_path.is_dir() == False:
            LOG_MSG.debug("model path is not a directory (%s)", model_path)
            return None

        if os.access(model_path, os.R_OK or os.W_OK or os.X_OK) == False:
            LOG_MSG.debug("access rights are wrong (%s)", model_path)
            return None

        # Make sure it's not empty
        if any(model_path.iterdir()) == False:
            LOG_MSG.debug("model directory is empty (%s)", model_path)
            return None

        if self.path_available(str(model_path)) == True:
            LOG_MSG.debug("model directory already in list (%s)", model_path)
            return None

        # Try to extract some information from the name
        locale_str=None
        model_type=None
        if model_path.name.startswith("vosk-model") == True:
            # Extract the locale from the filename and its type
            try:
                results=search("vosk-model(-small)?-(.+?)-", model_path.name)
                locale_str=_helper_locale_normalize(results.group(2))
                model_type=results.group(1)
                if model_type not in [None, ""]:
                    model_type=model_type[1:] # Removes starting "-"

            except AttributeError:
                # No locale found
                LOG_MSG.debug("non standard name format - no locale (%s)", model_path)
        else:
            LOG_MSG.debug("non stardard name format (%s)", model_path)

        # Deal with custom paths
        if model_path.parent not in MODEL_DIRS:
            # Only insert in paths dictionary
            model_desc=STTVoskModelDescription()
            model_desc.paths=[str(model_path)]
            model_desc.name=model_path.name
            model_desc.custom=True

            # The following migth not be available if the name is not right
            model_desc.locale=locale_str
            model_desc.type=model_type

            self._models_dict[str(model_path)]=model_desc
            self._model_paths_dict[str(model_path)]=model_desc

            LOG_MSG.debug("custom model directory is valid (%s)", model_path)

            # The locale is set afterwards and we signal the change once done
            return model_desc

        model_desc=self._models_dict.get(model_path.name, None)
        if model_desc is None:
            model_desc=STTVoskModelDescription()
            model_desc.paths=[str(model_path)]
            model_desc.locale=locale_str
            model_desc.type=model_type
            model_desc.name=model_path.name

            self._add_model_description_to_locale(model_desc)
            self._models_dict[model_desc.name]=model_desc
            self._model_paths_dict[str(model_path)]=model_desc

            LOG_MSG.debug("model directory is valid (%s) - name not known yet", model_path)
            self.emit("added", model_path.name, str(model_path))
            return model_desc

        # Note paths should be ordered by precedence as in MODEL_DIRS
        model_desc.paths.append(str(model_path))
        model_desc.paths.sort(key=lambda element : MODEL_DIRS.index(Path(element).parent))

        LOG_MSG.debug("model directory is valid (%s) - name already known", model_path)
        self.emit("added", model_path.name, str(model_path))
        return model_desc

    def _remove_model_description(self, model_path):
        model_desc = self._model_paths_dict.pop(model_path, None)
        if model_desc is None:
            return

        LOG_MSG.debug("model directory removed (%s)", model_path)

        model_desc.paths.remove(model_path)
        if any(model_desc.paths) == False:
            # Remove this model from locale list and locale list if none left
            models_list=self._locales_dict.get(model_desc.locale, [])
            models_list.remove(model_desc)
            if any(models_list) == False:
                self._locales_dict.pop(model_desc.locale, None)

            key=model_desc.name if model_desc.custom == False else model_path
            self._models_dict.pop(key, None)

        model_name=model_desc.name if model_desc.custom == False else None
        self.emit("removed", model_name, model_path)

    def _model_file_changed_cb(self, monitor, file, other_file, event_type):
        LOG_MSG.debug("a file changed (source = %s) %s %s", self, file.get_path(), event_type)

        if file.get_path() in MODEL_DIRS:
            LOG_MSG.debug("change does not concern a child of a top directory. Ignoring.")
            return

        LOG_MSG.info("a model file changed (%s) (event=%s)", file.get_path(), event_type)
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            # Make sure it is not a temporary directory (when we are downloading
            # a model)
            if file.get_path().endswith(DOWNLOADED_MODEL_SUFFIX):
                LOG_MSG.debug("temporary file ignored (%s)", file.get_path())
                return

            self._new_model_available(Path(file.get_path()))
        elif event_type == Gio.FileMonitorEvent.DELETED:
            self._remove_model_description(file.get_path())

    def _get_available_local_models(self):
        for directory in MODEL_DIRS:
            LOG_MSG.debug("scanning %s for models", directory)

            if directory is None:
                continue

            monitor=Gio.File.new_for_path(str(directory)).monitor(Gio.FileMonitorFlags.NONE, None)
            monitor.connect("changed", self._model_file_changed_cb)
            self._monitors.append(monitor)

            directory_path=Path(directory)
            if directory_path.is_dir() == False:
                continue

            for child in directory_path.iterdir():
                LOG_MSG.debug("scanning file (%s)", str(child))
                self._new_model_available(child)

    def path_available(self, model_path):
        return model_path in self._model_paths_dict

    def get_models_for_locale(self, locale_str):
        return self._locales_dict.get(locale_str, [])

    def get_best_path_for_model(self, model_name):
        if model_name is None:
            return None

        model=self._models_dict.get(model_name, None)
        if model is None:
            return None

        if model.paths in [None, []]:
            return None

        # First is always the best
        return model.paths[0]

    def get_model_description(self, model_name):
        return self._models_dict.get(model_name, None)

    def get_supported_locales(self):
        return list(self._locales_dict.keys())

    def _custom_model_file_changed_cb(self, monitor, file, other_file, event_type):
        # Note : we use monitor_file and therefore don't monitor children
        LOG_MSG.info("a custom model file changed (%s) (event=%s)", file.get_path(), event_type)
        if event_type == Gio.FileMonitorEvent.CHANGES_DONE_HINT:
            self._new_model_available(Path(file.get_path()))
        elif event_type == Gio.FileMonitorEvent.DELETED:
            model = self._model_paths_dict.get(file.get_path(), None)
            if model is None:
                return

            LOG_MSG.debug("custom model directory removed (%s)", file.get_path())
            self._model_paths_dict.pop(file.get_path(), None)
            self.emit("removed", None, file.get_path())

    def register_custom_model_path(self, model_path_str, locale_str):
        # Check it is not already in one of our directories
        if Path(model_path_str).parent in MODEL_DIRS:
            LOG_MSG.debug("registered a path in default directories (%s)", model_path_str)
            return

        monitor=self._custom_paths.get(model_path_str, None)
        if monitor is not None:
            monitor.refcount += 1
            LOG_MSG.debug("custom path already registered (%s). Increasing refcount (%i).", model_path_str, monitor.refcount)
            return

        monitor=Gio.File.new_for_path(model_path_str).monitor_file(Gio.FileMonitorFlags.NONE, None)
        monitor.connect("changed", self._custom_model_file_changed_cb)
        self._custom_paths[model_path_str]=monitor
        monitor.refcount=1

        model_desc=self._new_model_available(Path(model_path_str))
        model_desc.locale=locale_str
        self._add_model_description_to_locale(model_desc)

        # Don't rely on the name for these
        self.emit("added", None, model_path_str.rstrip("/"))

    def unregister_custom_model_path(self, model_path_str):
        # Check it is not already in one of our directories
        monitor=self._custom_paths.get(model_path_str, None)
        if monitor is None:
            LOG_MSG.debug("trying to unregister a path not in custom model paths (%s)", model_path_str)
            return

        if monitor.refcount != 1:
            LOG_MSG.debug("refcount of custom path not 0 yet (%s)", model_path_str)
            monitor.refcount -= 1
            return

        # Stop monitoring path and remove
        self._custom_paths.pop(model_path_str, None)
        self._remove_model_description(model_path_str)


_GLOBAL_LOCAL_MANAGER = None

def stt_vosk_local_model_manager():
    global _GLOBAL_LOCAL_MANAGER

    if _GLOBAL_LOCAL_MANAGER == None:
        _GLOBAL_LOCAL_MANAGER = STTVoskLocalModelManager()

    return _GLOBAL_LOCAL_MANAGER

def _helper_locale_normalize(locale_str):
    lang=locale_str[0:2].lower()
    if len(locale_str) < 5:
        return lang

    lang2=locale_str[3:5]
    return lang+"_"+lang2.upper()


class STTVoskOnlineModelManager(GObject.Object):
    __gtype_name__="STTVoskOnlineModelManager"

    __gsignals__={
        # TODO: we might want to change this to use a model instead of a string
        "added": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        "changed": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        "removed": (GObject.SIGNAL_RUN_FIRST, None, (object,)),
    }

    def __init__(self):
        super().__init__()

        self._locales_dict={}
        self._online_models={}

        # Allows to initialize it if it is not yet done
        local_manager=stt_vosk_local_model_manager()
        local_manager.connect("added", self._model_path_added_cb)
        local_manager.connect("removed", self._model_path_removed_cb)

        self._get_available_online_models()

    def _update_online_models_json(self):
        # Get the file with all models that can be downloaded
        LOG_MSG.debug("getting online list of models")

        try:
            with urllib.request.urlopen(MODEL_LIST_URL, timeout=3) as response:
                json_str=response.read()
                return json.loads(json_str)

        except:
            LOG_MSG.debug("an error occurred while retrieving the list of models")

        return None

    def _add_model_description_to_locale(self, model_desc):
        locale_models=self._locales_dict.get(model_desc.locale, None)
        if locale_models is None:
            self._locales_dict[model_desc.locale]=[model_desc]
        else:
            locale_models.append(model_desc)

    def _populate_with_online_models(self):
        online_models_json=self._update_online_models_json()
        if online_models_json in (None, {}, []):
            LOG_MSG.debug("impossible to retrieve the list of models online")
            return

        for description in online_models_json:
            model_desc=STTVoskModelDescription()
            model_desc.name=description.get("name","")
            model_desc.locale=_helper_locale_normalize(description.get("lang",""))
            model_desc.url=description.get("url","")
            model_desc.type=description.get("type","")
            model_desc.size=description.get("size_text","")
            model_desc.is_obsolete=bool(description.get("obsolete","") == "true")

            LOG_MSG.debug("adding online model (%s)", model_desc.name)

            # Don't check path as it cannot be a custom model
            local_desc=stt_vosk_local_model_manager().get_model_description(model_desc.name)
            if local_desc is not None:
                # Should we make a copy ?
                model_desc.paths=local_desc.paths

            self._online_models[model_desc.name]=model_desc
            self._add_model_description_to_locale(model_desc)

    def _get_available_online_models(self):
        LOG_MSG.debug("retrieving the list of models of online model manager")
        self._populate_with_online_models()

        # Populate with available local custom models
        # Note: it previous function fails then fill dict with local models
        # So don't assume we will always add custom model descriptions only
        for locale in stt_vosk_local_model_manager().get_supported_locales():
            model_list=stt_vosk_local_model_manager().get_models_for_locale(locale)
            LOG_MSG.debug("adding local models for locale (%s)", locale)
            for model_desc in model_list:
                key=model_desc.name if model_desc.custom == False else model_desc.paths[0]
                if key in self._online_models:
                    continue

                LOG_MSG.debug("adding local model to online dict (%s)", key)

                self._online_models[key]=model_desc
                self._add_model_description_to_locale(model_desc)

    def _model_path_added_cb(self, manager, model_name, model_path):
        # See if it is in dictionary (and then do nothing as the local manager
        # will have updated its paths).
        if model_name is not None:
            # online_model_desc should be known
            online_model_desc=self._online_models.get(model_name, None)
            local_model_desc=manager.get_model_description(model_name)
        else:
            online_model_desc=self._online_models.get(model_path, None)
            local_model_desc=manager.get_model_description(model_path)

        if online_model_desc is not None:
            # If that model description has paths already, no need to update the
            # paths for our online model description as it has the same list of
            # paths as the local model description
            if online_model_desc.paths in [None, []]:
                online_model_desc.paths=local_model_desc.paths

            self.emit("changed", online_model_desc)
            return

        # Apparently, it is still not in our database, add it.
        # Note: in this case, it is very likely a custom path was added but it
        # could also be that we did not manage to load the online list of models
        # and e are just duplicating the model descriptions of local manager.
        key=local_model_desc.name if local_model_desc.custom == False else local_model_desc.paths[0]
        self._online_models[key]=local_model_desc
        self._add_model_description_to_locale(local_model_desc)

        self.emit("added", local_model_desc)

    def _remove_model_description_from_locale(self, model_desc):
        locale_models=self._locales_dict.get(model_desc.locale, None)
        locale_models.remove(model_desc)
        if any(locale_models) == False:
            self._locales_dict.pop(model_desc.locale)

    def _model_path_removed_cb(self, manager, model_name, model_path):
        if model_name is None:
            # A custom path was dropped, just remove associated model
            # description. There can be only one path for such models.
            online_model_desc=self._online_models.pop(model_path, None)
            self._remove_model_description_from_locale(online_model_desc)
            self.emit("removed", online_model_desc)
            return

        # See if it is in the dictionary (and then do nothing as local manager
        # will have updated its paths).
        online_model_desc=self._online_models.get(model_name, None)
        if online_model_desc is None:
            return

        # Could be just a path removed, check
        if any(online_model_desc.paths) == True:
            self.emit("changed", online_model_desc)
            return

        # No more path so model description was removed from local dict
        # Keep it in our database, only if model has an url
        if online_model_desc.url is not None:
            self.emit("changed", online_model_desc)
            return

        # That should happen on rare occasions when we can't load online list
        self._online_models.pop(model_name, None)
        self._remove_model_description_from_locale(online_model_desc)

        self.emit("removed", online_model_desc)

    def get_model_description(self, model_name):
        return self._online_models.get(model_name, None)

    def get_models_for_locale(self, locale_str):
        return self._locales_dict.get(locale_str,[])

    def supported_locales(self):
        return list(self._locales_dict.keys())

_GLOBAL_ONLINE_MANAGER = None

def stt_vosk_online_model_manager():
    global _GLOBAL_ONLINE_MANAGER

    if _GLOBAL_ONLINE_MANAGER == None:
        _GLOBAL_ONLINE_MANAGER = STTVoskOnlineModelManager()

    return _GLOBAL_ONLINE_MANAGER
