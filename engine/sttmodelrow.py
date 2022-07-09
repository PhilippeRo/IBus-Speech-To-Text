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

from gettext import gettext as _

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib

from sttutils import *

from sttvoskmodelmanagers import STTDownloadState

LOG_MSG=logging.getLogger()


@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttmodelrow.ui")
class STTModelRow(Adw.ActionRow):
    __gtype_name__="STTModelRow"

    check_button = Gtk.Template.Child()
    model_button = Gtk.Template.Child()
    progress_bar = Gtk.Template.Child()

    def __init__(self, desc=None, model=None, row=None):
        super().__init__()

        self._desc=desc
        self._model=model
        self._model.connect("changed", self._model_changed_cb)

        self.update_description()

        # This is used in case a model is being downloaded when row is created
        if self._desc.download_progress!=STTDownloadState.STOPPED:
            self.model_button.set_icon_name("process-stop-symbolic")
            self.progress_bar.set_text(_("Downloading model"))
            self.progress_bar.set_visible(True)
            self._update_progress_bar()

            self._update_spinner_id=GLib.timeout_add(250, self._update_spinner)
        # No "else" here as we leave it to the spinner function to deal with end
        else:
            self._update_spinner_id=0

        if row is not None:
            self.check_button.set_group(row. check_button)
        else:
            self.check_button.set_group(None)

    def _update_progress_bar(self):
        if self._desc.download_progress >= STTDownloadState.ONGOING:
            self.progress_bar.set_fraction(self._desc.download_progress)
            return True

        if self._desc.download_progress == STTDownloadState.STOPPED:
            self.progress_bar.set_fraction(0.0)
            return False

        self.progress_bar.pulse()
        if self._desc.download_progress == STTDownloadState.UNPACKING:
            self.progress_bar.set_text(_("Unpacking model"))

        return True

    def _update_spinner(self):
        if self._update_progress_bar() == False:
            LOG_MSG.debug("download end")
            self._update_spinner_id=0
            self.progress_bar.set_visible(False)
            return False

        return True

    def _stop_downloading(self):
        self._desc.stop_downloading()

        self.progress_bar.set_visible(False)
        self.progress_bar.set_fraction(0.0)
        self.model_button.set_icon_name("folder-download-symbolic")

        if self._update_spinner_id != 0:
            GLib.Source.remove(self._update_spinner_id)
            self._update_spinner_id=0

    def _start_downloading(self):
        self.model_button.set_icon_name("process-stop-symbolic")
        self.progress_bar.set_text(_("Downloading model"))
        self.progress_bar.set_visible(True)

        self._update_spinner_id=GLib.timeout_add(250, self._update_spinner)
        self._desc.start_downloading()

    def _delete_model(self):
        self._desc.delete_paths()

    def _download_model(self):
        if self._desc.paths not in [None, []]:
            self._delete_model()
        elif self._desc.download_progress==STTDownloadState.STOPPED:
            self._start_downloading()
        else:
            LOG_MSG.info("cancelling downloading")
            self._stop_downloading()

    @Gtk.Template.Callback()
    def _download_model_button_clicked_cb(self, button):
        self._download_model()

    def update_description(self):
        # Don't let the user remove a model he has not installed himself
        # FIXME! Also only accept if file in right directory (cache)
        self.model_button.set_visible(self._desc.url not in ["", None])

        if self._desc.custom == True:
            self.set_title(_("%s - available on this computer") % self._desc.name)
            self.model_button.set_property("icon_name", "edit-delete-symbolic")
            self.set_subtitle(_("No description available. This is a custom model (name not found in online database)"))
            self._update_active_status()
            return

        # if there no path there has to be a URL
        if self._desc.paths in [None,[]]:
            title=_("%s - available for download") % self._desc.name
            self.model_button.set_property("icon_name", "folder-download-symbolic")
        else:
            title=_("%s - available on this computer") % self._desc.name
            self.model_button.set_property("icon_name", "edit-delete-symbolic")

        self.set_title(title)

        if self._desc.size in [None, ""]:
            size=_("unknown size")
        else:
            size=self._desc.size

        if self._desc.is_obsolete == True:
            description=_("This model is obsolete - %s") % size
        elif self._desc.type is not None:
            if self._desc.type.startswith("big") == True:
                description=_("Large model that may be more accurate than smaller ones - %s") % size
            else:
                description=_("Lightweight model for Android and RPi - %s") % size
        else:
            description=_("No description available for the current model (name not found in online database)")

        self.set_subtitle(description)
        self._update_active_status()

    def _check_model_path(self):
        if self._desc.custom == True:
            if any(self._desc.paths) == True:
                return bool(self._model.get_path() == self._desc.paths[0])
        elif self._desc.name is not None:
            return bool(self._model.get_name() == self._desc.name)

        return False

    def _update_active_status(self):
        is_active_model=self._check_model_path()
        if self.check_button.get_active() != is_active_model:
            self.check_button.set_active(is_active_model)

    def _model_changed_cb(self, model):
        self._update_active_status()

    @Gtk.Template.Callback()
    def check_button_toggled_cb(self, button):
        LOG_MSG.debug("check_button_toggled_cb (%s)", self._desc.name)
        if button.get_active() == True and self._check_model_path() == False:
            name=self._desc.name if self._desc.custom == False else self._desc.path
            self._model.set_name(name)

    def get_desc(self):
        return self._desc
