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


import gi

gi.require_version('Gtk', '4.0')

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Adw

@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttutterancerow.ui")
class STTUtteranceRow (Adw.ActionRow):
    __gtype_name__="STTUtteranceRow"

    __gsignals__ = {
        "delete": (GObject.SIGNAL_RUN_FIRST, None,())
    }

    delete_button=Gtk.Template.Child()

    def __init__(self, text="", editable=True):
        super().__init__()
        self.set_title(text)

        self.editable=editable
        self.text=text
        if editable == False:
            self.delete_button.set_visible(False)
            self.set_sensitive(False)

    @Gtk.Template.Callback()
    def delete_button_clicked_cb(self, button):
        self.emit("delete")

    def update(self):
        self.set_title(self.text.strip())
