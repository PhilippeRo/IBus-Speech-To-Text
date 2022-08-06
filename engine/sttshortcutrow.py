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

from gettext import gettext as _

import gi

gi.require_version('Gtk', '4.0')

from gi.repository import Gtk, GObject, Adw

@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttshortcutrow.ui")
class STTShortcutRow(Adw.ActionRow):
    __gtype_name__="STTShortcutRow"

    __gsignals__= {
        "delete": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "reset": (GObject.SIGNAL_RUN_FIRST, None, ())
    }

    reset_button = Gtk.Template.Child()
    remove_button = Gtk.Template.Child()
    revealer = Gtk.Template.Child()

    def __init__(self, value="", description="", utterances=None, extra_utterances=None, editable=False, pref_group=None):
        super().__init__()

        self.pref_group=pref_group
        self._value=value
        self._description=description
        self._original_description=description
        if utterances == None:
            self.utterances=[]
        else:
            self.utterances=utterances

        if extra_utterances == None:
            self._extra_utterances=[]
        else:
            self._extra_utterances=extra_utterances

        self.editable=editable
        self.update()

    @property
    def value(self):
        return self._value

    @property
    def description(self):
        return self._description

    @value.setter
    def value(self, value):
        if self.editable != True:
            return

        if self._value == value:
            return

        self._value = value
        self.update()

    @description.setter
    def description(self, description):
        if self._description == description:
            return

        self._description = description
        self.update()

    def _get_all_unique_utterances(self):
        touch= list(set(self.utterances)|set(self._extra_utterances))
        return touch

    def update(self):
        visible=bool(self.editable == False and (self._description != self._original_description or self._extra_utterances != []))
        self.revealer.set_reveal_child(visible)
        self.remove_button.set_visible(bool(self.editable == True))

        self.set_subtitle("\""+"\", \"".join(self._get_all_unique_utterances())+"\"")

        if self._description not in (None, ""):
            title=self._description
        elif isinstance(self._value, list):
            # This is for diacritics
            if len(self._value) == 1:
                title=self._value[0]
            else:
                title=self._value[1]
        else:
            title=self._value

        title=title.strip()
        if len(title) == 1:
            title = _("Character <span weight='heavy'>%s</span>") % title
        elif title.count("\n") >= 1:
            title = title.split("\n", 1)[0] + " …"

        self.set_title(title)

    @Gtk.Template.Callback()
    def remove_button_clicked_cb(self, button):
        self.emit("delete")

    @Gtk.Template.Callback()
    def reset_button_clicked_cb(self, button):
        self._description=self._original_description
        # Reset must come before we reset _extra_utterances since the utterances
        # has to be removed before.
        self.emit("reset")

        self._extra_utterances=[]
        self.update()

    def set_extra_utterances(self, utterances):
        self._extra_utterances=utterances
        self.update()

    def add_extra_utterances(self, utterances):
        if utterances == None:
            return

        for utterance in utterances:
            if utterance not in self._extra_utterances:
                self._extra_utterances.append(utterance)

        self.update()

    def get_json_data(self):
        if self.editable == False and self._description == self._original_description and self._extra_utterances == []:
            return None

        json_data={}

        # Value cannot be changed (unless it is a custom shortcut
        json_data["value"]=self._value

        if self.editable == True or \
           self._description not in("", self._original_description):
            json_data["description"]=self._description

        if self.editable == True or self._extra_utterances != []:
            json_data["utterances"]=self._extra_utterances

        return json_data
