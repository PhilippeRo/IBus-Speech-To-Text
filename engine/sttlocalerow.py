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

import locale
import logging

from gettext import gettext as _

from babel import Locale, UnknownLocaleError

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw

from sttutils import *

from sttvoskmodel import STTVoskModel
from sttmodelchooserdialog import STTModelChooserDialog
from sttvoskmodelmanagers import stt_vosk_online_model_manager


LOG_MSG=logging.getLogger()

@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttlocalerow.ui")
class STTLocaleRow(Adw.ActionRow):
    __gtype_name__="STTLocaleRow"

    check_button = Gtk.Template.Child()

    def __init__(self, current_locale=None, locale_str=None, radio_group=None):
        super().__init__()
        if locale_str == None:
            LOG_MSG.error("no locale provided")
            return

        self._locale=locale_str
        system_locale_str=locale.getlocale()[0]
        try:
            babel_locale=Locale.parse(locale_str)
            name=babel_locale.get_display_name(system_locale_str)
        except UnknownLocaleError:
            name=locale_str

        if system_locale_str == self._locale:
            name = _("%s : system locale") % name

        self.set_title(name)

        self._current_locale = current_locale

        self._update_checked()
        self._current_locale.connect("changed", self._locale_changed)

        self._model = STTVoskModel(locale_str=self._locale)
        self._model.connect("changed", self._model_changed)
        self.update_description()

        self.check_button.set_group(radio_group)

    @property
    def locale(self):
        return self._locale

    @Gtk.Template.Callback()
    def check_button_toggled_cb(self, button):
        LOG_MSG.debug("check_button_toggled_cb (%s)", self._locale)
        if button.get_active() == self._current_locale.default_locale:
            return

        if button.get_active() == True:
            self._current_locale.locale=self._locale

    def _update_checked(self):
        is_current_locale=bool(self._current_locale.locale == self._locale)
        if self.check_button.get_active() != is_current_locale:
            self.check_button.set_active(is_current_locale)

    def _locale_changed(self, current_locale):
        self._update_checked()

    def manage_model(self):
        window=STTModelChooserDialog(model=self._model)
        window.set_transient_for(self.get_root())
        window.present()

    @Gtk.Template.Callback()
    def _manage_model_button_clicked_cb(self, button):
        self.manage_model()

    def update_description(self):
        if self._model.available() == False:
            self.set_subtitle(_("No model downloaded yet"))
            return

        model_name=self._model.get_name()
        if model_name in [None, ""]:
            self.set_subtitle(_("Custom model installed manually in a non-standard directory"))
            return

        model=stt_vosk_online_model_manager().get_model_description(model_name)
        if model is None:
            size=_("unknown size")
        else:
            size=model.size

        description=""
        if model.is_obsolete == True:
            description=_("This model is obsolete - %s") % size
        elif model.type is not None:
            if model.type.startswith("big") == True:
                description=_("Large model that may be more accurate than smaller ones - %s") % size
            else:
                description=_("Lightweight model for Android and RPi - %s") % size
        else:
            description=_("No description available for the current model (name not found in online database)")

        self.set_subtitle(description)

    def _model_changed(self, model):
        self.update_description()
