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

gi.require_version('Gtk', '4.0')

from gi.repository import Gtk, Adw

from sttutterancerow import STTUtteranceRow
from sttshortcutrow import STTShortcutRow

LOG_MSG=logging.getLogger()

@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttshortcutdialog.ui")
class STTShortcutDialog(Gtk.Dialog):
    __gtype_name__="STTShortcutDialog"

    add_button=Gtk.Template.Child()
    apply_button=Gtk.Template.Child()
    add_utterance_button=Gtk.Template.Child()
    apply_utterance_button=Gtk.Template.Child()
    previous_button=Gtk.Template.Child()
    cancel_button=Gtk.Template.Child()

    text_view=Gtk.Template.Child()
    description_entry = Gtk.Template.Child()

    button_stack_start=Gtk.Template.Child()
    button_stack_end=Gtk.Template.Child()

    utterance_list=Gtk.Template.Child()
    utterance_entry=Gtk.Template.Child()

    text_label=Gtk.Template.Child()

    contents=Gtk.Template.Child()
    header=Gtk.Template.Child()

    alternatives_list=Gtk.Template.Child()
    recognize_toggle=Gtk.Template.Child()

    def __init__(self, row=None, engine=None, **kwargs):
        super().__init__(**kwargs)

        self._row=row
        self._added_temp={}
        self._removed_temp={}
        self._rows_list=[]
        self._activated_row=None

        self.button_stack_start.set_visible_child(self.cancel_button)

        buffer = self.utterance_entry.get_buffer()
        buffer.connect("notify::text", self.utterance_text_changed)

        buffer=self.text_view.get_buffer()
        buffer.connect("notify::text", self.value_text_changed)

        # I don't know why but we need this ??? Otherwise it does not show up.
        self.set_titlebar(self.header)

        self._engine=engine
        engine.connect("model-changed", self._model_changed_cb)
        engine.connect("state", self._state_changed_cb)
        if engine.has_model() == False:
            self.recognize_toggle.set_sensitive(False)
        self._update_recognize_button()

        self._alternative_rows=[]
        self._recognition_id=0

        if row == None:
            # It's a new empty shortcut
            self.utterances = []
            self.add_button.set_sensitive(False)
            self.button_stack_end.set_visible_child(self.add_button)
            return

        self.utterances = row.utterances
        self.button_stack_end.set_visible_child(self.apply_button)

        buffer=self.description_entry.get_buffer()
        if row.description not in (None, ""):
            buffer.set_text(row.description,-1)
        buffer.connect("notify::text", self.description_changed)

        if isinstance(row.value, list):
            # For diacritics
            if len(row.value) == 1:
                value = row.value[0]
            else:
                value = row.value[1]
        else:
            value=row.value

        if value not in (None, ""):
            buffer=self.text_view.get_buffer()
            buffer.set_text(value,-1)

        if row.editable == False:
            # It's a default shortcut
            self.text_view.set_sensitive(False)
            self.button_stack_end.set_visible_child(self.apply_button)

            # For these row if there is a description, keep it
            if row.description not in (None,""):
                self.text_label.set_visible(False)

        unique_utterances=list(set(row.utterances)|set(row._extra_utterances))
        for utterance in unique_utterances:
            utterance_row=STTUtteranceRow(text=utterance, editable=bool(utterance not in row.utterances))
            self.utterance_list.add(utterance_row)
            utterance_row.connect("activated", self.row_activated_cb)
            utterance_row.connect("delete", self.row_deleted_cb)
            self._rows_list.append(utterance_row)

    def row_activated_cb(self, row):
        self._activated_row=row
        buffer=self.utterance_entry.get_buffer()
        buffer.set_text(row.text, -1)

        self.contents.set_visible_child_name("utterance")
        self.button_stack_start.set_visible_child(self.previous_button)
        self.button_stack_end.set_visible_child(self.apply_utterance_button)
        self.set_default_widget(self.apply_utterance_button)

    @Gtk.Template.Callback()
    def new_utterance_button_clicked_cb(self, button):
        self._activated_row=None
        buffer=self.utterance_entry.get_buffer()
        buffer.set_text("", -1)

        self.utterance_entry.set_placeholder_text("Type your utterance")

        self.contents.set_visible_child_name("utterance")
        self.button_stack_start.set_visible_child(self.previous_button)
        self.button_stack_end.set_visible_child(self.add_utterance_button)
        self.set_default_widget(self.add_utterance_button)

        self.add_utterance_button.set_sensitive(False)

    @Gtk.Template.Callback()
    def new_alternative_utterances_button_clicked_cb(self, button):
        self._activated_row=None

        self.contents.set_visible_child_name("utterance_recognition")
        self.button_stack_start.set_visible_child(self.previous_button)
        self.button_stack_end.set_visible_child(self.add_utterance_button)
        self.set_default_widget(self.add_utterance_button)

        for row in self._alternative_rows:
            self.alternatives_list.remove(row)
        self._alternative_rows=[]

        self.add_utterance_button.set_sensitive(False)
        self.recognize_toggle.grab_focus()

    def display_global_page(self):
        self._activated_row=None

        self.contents.set_visible_child_name("global")
        self.button_stack_start.set_visible_child(self.cancel_button)

        if self._row == None:
            self.button_stack_end.set_visible_child(self.add_button)
            self.set_default_widget(self.add_button)
        else:
            self.button_stack_end.set_visible_child(self.apply_button)
            self.set_default_widget(self.apply_button)

        for row in self._alternative_rows:
            self.alternatives_list.remove(row)

        self._alternative_rows=[]

        self._stop_recognition()

    @Gtk.Template.Callback()
    def previous_button_clicked_cb(self, button):
        self.display_global_page()

    def _add_utterance_row(self, utterance):
        # Utterance can't be in _added_temp (we checked it while it was typed)
        if self._removed_temp.get(utterance) == True:
            self._removed_temp.pop(utterance)
        else:
            self._added_temp[utterance]=True

        utterance_row=STTUtteranceRow(text=utterance, editable=bool(utterance not in self.utterances))
        self.utterance_list.add(utterance_row)
        utterance_row.connect("delete", self.row_deleted_cb)
        utterance_row.connect("activated", self.row_activated_cb)
        self._rows_list.append(utterance_row)

    def _add_utterance_from_listbox(self):
        for row in self._alternative_rows:
            if row.get_icon_name() != None and row.get_icon_name() != "":
                self.alternatives_list.remove(row)
                continue

            self._add_utterance_row(row.get_title())
            self.alternatives_list.remove(row)

        self._alternative_rows=[]

        self._update_add_apply_buttons_state()
        self.display_global_page()

    def _add_utterance_from_entry(self):
        buffer=self.utterance_entry.get_buffer()
        utterance=buffer.get_text()

        self._add_utterance_row(utterance)
        self._update_add_apply_buttons_state()

        self.display_global_page()

    @Gtk.Template.Callback()
    def add_utterance_button_clicked_cb(self, button):
        if self.contents.get_visible_child_name() == "utterance":
            self._add_utterance_from_entry()
        else:
            self._add_utterance_from_listbox()

    @Gtk.Template.Callback()
    def apply_utterance_button_clicked_cb(self, button):
        # If the button has been clicked, the text HAS been modified
        buffer=self.utterance_entry.get_buffer()
        utterance=buffer.get_text()

        # Utterance can't be in _added_temp (we checked it while it was typed)
        if self._removed_temp.get(utterance) == True:
            self._removed_temp.pop(utterance)
        else:
            self._added_temp[utterance]=True

        if self._added_temp.get(self._activated_row.text) == True:
            self._added_temp.pop(self._activated_row.text)
        else:
            self._removed_temp[self._activated_row.text]=True

        self._activated_row.text=utterance
        self._activated_row.update()

        self.display_global_page()

    def row_deleted_cb(self, row):
        if self._added_temp.get(row.text) == True:
            self._added_temp.pop(row.text)
        else:
            self._removed_temp[row.text]=True

        self.utterance_list.remove(row)
        self._rows_list.remove(row)
        self._update_add_apply_buttons_state()

    def apply_to_row(self):
        # We don't set value unless it's editable
        if self._row.editable:
            LOG_MSG.debug("row is editable")
            # we don't need to be careful about diacritics here as value
            # won't be changed.
            buffer=self.text_view.get_buffer()
            self._row.value=buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
            LOG_MSG.debug("row value %s", self._row.value)

        buffer=self.description_entry.get_buffer()
        self._row.description=buffer.get_text()

        extra=[]
        for row in self._rows_list:
            extra.append(row.text)

        self._row.set_extra_utterances(extra)
        return (self._added_temp, self._removed_temp)

    def get_new_row(self):
        buffer=self.text_view.get_buffer()
        value=buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

        buffer=self.description_entry.get_buffer()
        description=buffer.get_text()

        extra=[]
        for row in self._rows_list:
            extra.append(row.text)

        return STTShortcutRow(value=value,
                              extra_utterances=extra,
                              description=description,
                              editable=True)

    def _check_utterance_existence(self, utterance):
        parent = self.get_transient_for()
        if utterance == "" :
            sensitive=False
            show_warning=False
        elif parent._utterances_dict.get(utterance, False) == True or self._added_temp.get(utterance) == True:
            sensitive=False
            show_warning=bool(self._activated_row == None or utterance != self._activated_row.text)
        else:
            sensitive=True
            show_warning=False

        return (sensitive, show_warning)

    def utterance_text_changed(self, buffer, text):
        utterance = buffer.get_text()
        (sensitive, show_warning) = self._check_utterance_existence(utterance)

        if show_warning == True:
            self.utterance_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "dialog-warning-symbolic")
            self.utterance_entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "The utterance already exists")
        else:
            self.utterance_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, None)
            self.utterance_entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, None)

        button=self.button_stack_end.get_visible_child()
        self.set_default_widget(button)
        button.set_sensitive(sensitive)

    def _update_add_apply_buttons_state(self):
        buffer=self.text_view.get_buffer()
        value=buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

        buffer=self.description_entry.get_buffer()
        description=buffer.get_text()

        parent = self.get_transient_for()
        if value == "" :
            # No value typed
            sensitive=False
            LOG_MSG.info("no value")
        elif len(self._rows_list) == 0:
            # No utterance
            sensitive=False
            LOG_MSG.info("no utterance")
        elif parent._values_dict.get(value, None) == None:
            # Value is not known in any other shortcut: it's either new or changed
            sensitive=True
            LOG_MSG.info("new value")
        elif self._row == None:
            # That's a new shortcut, so if value is known it means it exists
            sensitive=False
            LOG_MSG.info("new shortcut")
        elif value != self._row.value:
            # It means that it's not the original value and that it is known
            sensitive=False
            LOG_MSG.info("value already exists")
        elif self._row.description != description:
            # Same value, same description
            sensitive=True
            LOG_MSG.info("description has changed")
        elif len(self._removed_temp) != 0 or len (self._added_temp) != 0:
            sensitive=True
            LOG_MSG.info("new or removed utterance")
        else:
            LOG_MSG.info("nothing has changed")
            sensitive=False

        self.add_button.set_sensitive(sensitive)
        self.apply_button.set_sensitive(sensitive)

    def value_text_changed(self, buffer, text):
        self._update_add_apply_buttons_state()

    def description_changed(self, buffer, text):
        self._update_add_apply_buttons_state()

    def _stop_recognition(self):
        if self._recognition_id != 0:
            self._engine.disconnect(self._recognition_id)
            self._recognition_id=0

        self._engine.stop()

    def _new_utterance_row_delete_clicked_cb(self, button):
        row=button.get_parent()
        while isinstance(row, Adw.ActionRow):
            row=row.get_parent()
            if row == None:
                return

        self.alternatives_list.remove(row)
        self._alternative_rows.remove(row)
        if len(self._alternative_rows) == 0:
            self.add_utterance_button.set_sensitive(False)

    def _alternatives_cb(self, engine, alternatives):
        LOG_MSG.debug("alternatives utterances")

        for row in self._alternative_rows:
            self.alternatives_list.remove(row)

        self._alternative_rows=[]

        num_valid_utterances = 0
        for utterance in alternatives:
            row=Adw.ActionRow()

            row.set_title(utterance)
            delete_button=Gtk.Button()
            delete_button.set_icon_name("edit-clear-symbolic")
            delete_button.set_property("hexpand", True)
            delete_button.set_property("halign", Gtk.Align.END)
            delete_button.set_property("valign", Gtk.Align.CENTER)
            style_context=delete_button.get_style_context()
            style_context.add_class("circular")
            style_context.add_class("flat")
            delete_button.connect("clicked", self._new_utterance_row_delete_clicked_cb)
            row.add_suffix(delete_button)

            self.alternatives_list.append(row)
            self._alternative_rows.append(row)

            # Check if utterance exists
            (sensitive, utterance_exists)=self._check_utterance_existence(utterance)
            if utterance_exists == False:
                num_valid_utterances += 1
            else:
                row.set_icon_name("dialog-warning-symbolic")
                row.set_subtitle("The utterance already exists")

        self._stop_recognition()

        if num_valid_utterances > 0:
            self.add_utterance_button.set_sensitive(True)

    def _update_recognize_button(self):
        if self._engine.is_running() == True:
            self.recognize_toggle.set_icon_name("media-playback-stop-symbolic")
        elif self._engine.has_model() == True:
            self.recognize_toggle.set_icon_name("microphone-sensitivity-high-symbolic")
        else:
            spinner=Gtk.Spinner()
            self.recognize_toggle.set_child(spinner)
            spinner.start()

    def _state_changed_cb(self, engine):
        self._update_recognize_button()

    @Gtk.Template.Callback()
    def recognize_alternatives_clicked_cb(self, button):
        if self._engine.is_running() == True:
            self._engine.get_final_results()
            self._stop_recognition()
            return

        self.add_utterance_button.set_sensitive(False)

        for row in self._alternative_rows:
            self.alternatives_list.remove(row)

        self._alternative_rows=[]

        self._recognition_id=self._engine.connect("alternatives", self._alternatives_cb)
        self._engine.set_alternatives_num(5)

        self._engine.run()

    def _model_changed_cb(self, engine):
        self._update_recognize_button()
        self.recognize_toggle.set_sensitive(self._engine.has_model())
