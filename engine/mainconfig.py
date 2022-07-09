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

#!/bin/python
import sys
import os

import locale
import gettext
import logging

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gst', '1.0')

from gi.repository import GLib

GLib.set_prgname('ibus-setup-stt')
GLib.set_application_name('ibus-setup-stt')

from gi.repository import Gio
from gi.repository import Adw
from gi.repository import Gst

from sttutils import stt_utils_get_system_data_path

class Application(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.win=None

    def do_activate(self):
        if self.win == None:
            # We import it here as GResource must be loaded before
            from sttconfigdialog import STTConfigDialog
            self.win = STTConfigDialog(application=self)
        self.win.present()

if __name__ == "__main__":

    LOG_MSG=logging.getLogger()
    msg_handler=logging.StreamHandler()
    msg_formatter=logging.Formatter(#'%(asctime)s '
                                    '%(levelname)s:\t'
                                    '%(filename)s:%(lineno)d:%(funcName)s:\t'
                                    '%(message)s')
    msg_handler.setFormatter(msg_formatter)
    LOG_MSG.addHandler(msg_handler)
    LOG_MSG.setLevel(logging.DEBUG)

    LOG_MSG.debug("Starting")

    # This must be loaded BEFORE the import of sttconfigdialog
    resource = Gio.Resource.load(os.path.join(stt_utils_get_system_data_path(), 'ibus-engine-stt-config.gresource'))
    resource._register()

    Gst.init(sys.argv)

    gettext.bindtextdomain('ibus-stt')
    gettext.textdomain('ibus-stt')
    locale.bindtextdomain('ibus-stt', None)
    locale.textdomain('ibus-stt')

    app = Application(application_id='org.freedesktop.ibus.stt.setup',
                      flags=Gio.ApplicationFlags.FLAGS_NONE)
    return_value=app.run(sys.argv)

    sys.exit(return_value)
