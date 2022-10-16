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

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Adw

@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttutterancerow.ui")
class STTUtteranceRow (Adw.EntryRow):
    __gtype_name__="STTUtteranceRow"

    __gsignals__ = {
        "delete": (GObject.SIGNAL_RUN_FIRST, None,()),
        "text-changed": (GObject.SIGNAL_RUN_FIRST, None,(str,str)),
    }

    delete_button=Gtk.Template.Child()
    valid_image=Gtk.Template.Child()

    def __init__(self, text="", editable=True):
        super().__init__()

        self.editable=editable
        self.text=text
        self.set_title(self.text)
        if editable == False:
            self.delete_button.set_visible(False)
            self.set_sensitive(False)

        self.editing=False
        self._focus_controller=Gtk.EventControllerFocus.new()
        self.add_controller(self._focus_controller)
        self._focus_controller.connect_after("leave", self.leave_event)
        self._focus_controller.connect("enter", self.enter_event)

        self.connect("entry-activated", self.activated_cb)

    @Gtk.Template.Callback()
    def delete_button_clicked_cb(self, button):
        self.emit("delete")

    def _validate_utterance(self):
        if self.editing == False:
            return

        self.editing=False
        # default handler, used to update the value of self.text
        text=self.get_text()
        if self.text != text or text in ["", None]:
            self.emit("text-changed", self.text, text)
            self.text=text

        self.set_title(text)

        # Reset to nothing
        self.set_text("")

    # do_activated does not seem possible as there is no virtual method
    def activated_cb(self, row):
        self._validate_utterance()

    def enter_event(self, controller):
        self.editing=True
        self.set_text(self.text)
        self.set_title("")
        if self.text in [None,""]:
            delegate=self.get_delegate()
            delegate.set_placeholder_text(_("Type your utterance"))
            self.valid_image.set_visible(True)

    def leave_event(self, controller):
        self._validate_utterance()
