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

from gi.repository import Gtk

from sttmodelrow import STTModelRow
from sttvoskmodelmanagers import stt_vosk_online_model_manager

LOG_MSG=logging.getLogger()

def _helper_merge_online_choices(models_dict, online_models):
    for model in online_models:
        local_model=models_dict.get(model.name, None)
        if local_model is not None:
            local_model.url=model.url
            local_model.size=model.size
            local_model.type=model.type
            local_model.is_obsolete=model.is_obsolete
        else:
            models_dict[model.name]=model

@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttmodelchooserdialog.ui")
class STTModelChooserDialog(Gtk.Dialog):
    __gtype_name__="STTModelChooserDialog"

    model_list=Gtk.Template.Child()
    obsolete_button=Gtk.Template.Child()

    def __init__(self, model=None, **kwargs):
        super().__init__(**kwargs)

        self._model_dict={}

        self._model=model

        locale_str=model.get_locale()
        full_list=[]
        full_list+=stt_vosk_online_model_manager().get_models_for_locale(locale_str)
        if len(locale_str) > 2:
            full_list+=stt_vosk_online_model_manager().get_models_for_locale(locale_str[:2])

        LOG_MSG.debug("%i available models for %s", len(full_list), locale_str)
        for model_desc in full_list:
            self._add_row(model_desc)

        self._added_id=stt_vosk_online_model_manager().connect("added", self._model_path_added_cb)
        self._changed_id=stt_vosk_online_model_manager().connect("changed", self._model_path_changed_cb)
        self._removed_id=stt_vosk_online_model_manager().connect("removed", self._model_path_removed_cb)

    def _add_row(self, model_desc):
        # Get first button available for the radio_group
        other_row=next(iter(self._model_dict.values())) if any(self._model_dict.values()) else None
        row=STTModelRow(desc=model_desc, model=self._model, row=other_row)
        self._model_dict[id(model_desc)]=row

        if model_desc.is_obsolete == True and row.check_button.get_active() == False:
            row.set_visible(self.obsolete_button.get_active())

        self.model_list.add(row)

    def _model_path_added_cb(self, manager, model_desc):
        # Check if it is the right locale
        if model_desc.locale != self._model.get_locale():
            return

        self._add_row(model_desc)

    def _model_path_changed_cb(self, manager, model_desc):
        # Check if model path or name is already in the list and update
        row=self._model_dict.get(id(model_desc), None)
        if row is not None:
            row.update_description()

    def _model_path_removed_cb(self, manager, model_desc):
        # Check if model path or name is already in the list
        row=self._model_dict.get(id(model_desc), None)
        if row is not None:
            self.model_list.remove(row)

    @Gtk.Template.Callback()
    def obsolete_button_toggled_cb(self, button):
        show_obsolete=button.get_active()
        for row in self._model_dict.values():
            if row.get_desc().is_obsolete == True and row.check_button.get_active() == False:
                row.set_visible(show_obsolete)

    def _open_locale_file_cb(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            dialog.destroy()
            return

        file=dialog.get_file()
        dialog.destroy()
        self._model.set_name(file.get_path())

    @Gtk.Template.Callback()
    def new_model_button_clicked_cb(self, button):
        root_widget=self.get_root()
        dialog=Gtk.FileChooserDialog(transient_for=root_widget, title=_("Open Model"), modal=True, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL, _("Open"), Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self._open_locale_file_cb)
        dialog.set_transient_for(root_widget)
        dialog.present()
