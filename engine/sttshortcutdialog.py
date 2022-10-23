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
gi.require_version('Adw', '1')

from gi.repository import GLib, Gtk, Adw

from sttutterancerow import STTUtteranceRow
from sttshortcutrow import STTShortcutRow

LOG_MSG=logging.getLogger()

@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttshortcutdialog.ui")
class STTShortcutDialog(Gtk.Dialog):
    __gtype_name__="STTShortcutDialog"

    add_button=Gtk.Template.Child()
    apply_button=Gtk.Template.Child()
    cancel_button=Gtk.Template.Child()

    text_view=Gtk.Template.Child()
    description_entry = Gtk.Template.Child()

    button_stack_end=Gtk.Template.Child()

    utterance_list=Gtk.Template.Child()

    text_label=Gtk.Template.Child()

    header=Gtk.Template.Child()

    new_alternative_utterances_button=Gtk.Template.Child()

    def __init__(self, row=None, engine=None, **kwargs):
        super().__init__(**kwargs)

        self._row=row
        self._added_temp={}
        self._removed_temp={}
        self._changes=0
        self._rows_list=[]

        self.connect("response",self._response)

        buffer=self.text_view.get_buffer()
        buffer.connect("notify::text", self._value_text_changed)

        # We need this; Otherwise our titlebar does not show up.
        self.set_titlebar(self.header)

        self._engine=engine
        engine.connect("model-changed", self._model_changed_cb)
        engine.connect("state-changed", self._state_changed_cb)
        if engine.has_model() == False:
            self.new_alternative_utterances_button.set_sensitive(False)
        self._update_recognize_button()

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
        buffer.connect("notify::text", self._description_changed)

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
            self._add_utterance_row(utterance_row)

    def _response (self, dialog, response_type):
        # Make sure any recognition is stopped when dialog is about to be closed
        self._stop_recognition()

    def _delete_utterance(self, utterance):
        num_rows=self._added_temp.get(utterance, 0)
        num_rows -= 1

        if num_rows == 0:
            self._added_temp.pop(utterance)

            parent = self.get_transient_for()
            if parent._utterances_dict.get(utterance, False) is False:
                self._changes -= 1
        elif num_rows == -1:
            self._removed_temp[utterance]=True
            self._changes += 1
        else:
            self._added_temp[utterance]=num_rows

    def _add_utterance(self, utterance):
        if self._removed_temp.get(utterance) == True:
            self._removed_temp.pop(utterance)
            self._changes -= 1
        else:
            num_rows=self._added_temp.get(utterance, 0)
            num_rows+=1
            self._added_temp[utterance]=num_rows

            parent = self.get_transient_for()
            if num_rows == 1 and \
               parent._utterances_dict.get(utterance, False) is False:
               self._changes += 1

    def _check_utterance_existence(self, utterance_row, utterance):
        if utterance in ["", None] :
            return False

        parent = self.get_transient_for()
        num_rows=self._added_temp.get(utterance, 0)
        if parent._utterances_dict.get(utterance, False) == True and self._removed_temp.get(utterance, False) == False:
            num_rows += 1

        if num_rows != 0:
            if utterance_row is None:
                return True

            return bool(num_rows == 1 and utterance != utterance_row.text)

        return False

    def _update_focus(self):
        if self._row == None:
            button=self.add_button
        else:
            button=self.apply_button

        if button.get_sensitive() == False:
            self.cancel_button.grab_focus()
            self.set_default_widget(self.cancel_button)
        else:
            button.grab_focus()
            self.set_default_widget(button)

    def _remove_row_real(self, utterance_row):
        self.utterance_list.remove(utterance_row)

    def _remove_utterance_row(self, utterance_row):
        # Make sure it cannot be removed twice
        if utterance_row not in self._rows_list:
            return

        utterance_row.disconnect_by_func(self.utterance_row_text_changed_cb)
        utterance_row.disconnect_by_func(self.utterance_row_activated_cb)
        utterance_row.disconnect_by_func(self.utterance_text_changed)
        utterance_row.disconnect_by_func(self.row_deleted_cb)
        self._rows_list.remove(utterance_row)

        # Unfortunately, this triggers a warning message but it would help
        # make sure the row cannot be changed anymore.
        # utterance_row.set_sensitive(False)

        # This is the only way to avoid an infinite loop if we remove the row
        # after it receives a "leave" signal from the event controller
        GLib.idle_add(self._remove_row_real, utterance_row)

    def delete_row(self, utterance_row):
        if utterance_row.text not in [None,""]:
            self._delete_utterance(utterance_row.text)

        self._remove_utterance_row(utterance_row)
        self._update_add_apply_buttons_state()
        self._update_focus()

    def row_deleted_cb(self, utterance_row):
        self.delete_row(utterance_row)

    def utterance_row_text_changed_cb(self, utterance_row, old_text, new_text):
        # If old_text is empty then it is a new row
        if old_text not in [None,""]:
            self._delete_utterance(old_text)

        # If new_text is empty, delete row
        if new_text in [None,""]:
            self._remove_utterance_row(utterance_row)
        elif self._check_utterance_existence(None, new_text):
            self._remove_utterance_row(utterance_row)
        else:
            self._add_utterance(new_text)
        self._update_add_apply_buttons_state()

    def utterance_row_activated_cb(self, utterance_row):
        self._update_focus()

    def _add_utterance_row(self, utterance_row):
        self.utterance_list.add(utterance_row)
        utterance_row.connect("text-changed", self.utterance_row_text_changed_cb)
        utterance_row.connect("entry-activated", self.utterance_row_activated_cb)
        utterance_row.connect("changed", self.utterance_text_changed)
        utterance_row.connect("delete", self.row_deleted_cb)
        self._rows_list.append(utterance_row)

    @Gtk.Template.Callback()
    def new_utterance_button_clicked_cb(self, button):
        utterance_row=STTUtteranceRow()
        self._add_utterance_row(utterance_row)
        utterance_row.grab_focus()

    def utterance_text_changed(self, utterance_row):
        if utterance_row.editing == False:
            return

        utterance = utterance_row.get_text()
        show_warning = self._check_utterance_existence(utterance_row, utterance)
        utterance_row.valid_image.set_visible(show_warning)

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
        elif self._changes != 0:
            sensitive=True
            LOG_MSG.info("new or removed utterance")
        else:
            LOG_MSG.info("nothing has changed")
            sensitive=False

        if self._row == None:
            button=self.add_button
        else:
            button=self.apply_button

        button.set_sensitive(sensitive)

    def _value_text_changed(self, buffer, text):
        self._update_add_apply_buttons_state()

    def _description_changed(self, buffer, text):
        self._update_add_apply_buttons_state()

    def _stop_recognition(self):
        if self._recognition_id != 0:
            self._engine.disconnect(self._recognition_id)
            self._recognition_id=0

        self._engine.stop()

    def _alternatives_cb(self, engine, alternatives):
        LOG_MSG.debug("alternatives utterances")
        for utterance in alternatives:
            # Check if utterance exists
            if self._check_utterance_existence(None, utterance) == True:
                continue

            utterance_row=STTUtteranceRow(text=utterance, editable=True)
            self._add_utterance_row(utterance_row)
            self._add_utterance(utterance)

        self._update_add_apply_buttons_state()

        self._stop_recognition()

    def _update_recognize_button(self):
        if self._engine.is_running():
            self.new_alternative_utterances_button.set_icon_name("media-playback-stop-symbolic")
        elif self._engine.has_model() == True:
            self.new_alternative_utterances_button.set_icon_name("microphone-sensitivity-high-symbolic")
        else:
            self.new_alternative_utterances_button.set_icon_name("microphone-sensitivity-muted-symbolic")

    def _state_changed_cb(self, engine):
        self._update_recognize_button()

    @Gtk.Template.Callback()
    def recognize_alternatives_clicked_cb(self, button):
        if self._engine.is_running() == True:
            self._engine.get_final_results()
            self._stop_recognition()
            return

        self._recognition_id=self._engine.connect("alternatives", self._alternatives_cb)
        self._engine.set_alternatives_num(5)
        self._engine.run()

    def _model_changed_cb(self, engine):
        self._update_recognize_button()
        self.new_alternative_utterances_button.set_sensitive(self._engine.has_model())

    # Called by STTConfigDialog to update a STTShortcutRow
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
            # All utterances cannot be removed nor changed
            if row.text in self._row.utterances:
                continue

            extra.append(row.text)

        self._row.set_extra_utterances(extra)
        return (self._added_temp, self._removed_temp)

    # Called by STTConfigDialog to get a new STTShortcutRow
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
