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
import sys
import locale
import logging

from gettext import gettext as _

import gi

gi.require_version('Gst', '1.0')
gi.require_version('IBus', '1.0')

from gi.repository import IBus
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gst

from sttutils import *
from sttengine import STTEngine
from sttgstfactory import stt_gst_factory_default

LOG_MSG=logging.getLogger()

class IMApplication(Gio.Application):
    __gtype_name__ = 'IMApplication'

    def __init__(self):
        LOG_MSG.info("Init")
        super().__init__(application_id=stt_utils_get_app_id(),
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE|
                               Gio.ApplicationFlags.ALLOW_REPLACEMENT)

        self.__exec_by_ibus=False
        self.__daemonize=False

        self.__bus=None
        self.__factory=None
        self.__component=None

    def do_handle_local_options(self, options):
        LOG_MSG.info("Local options parsing")

        # These options are always local and should only be useful if we are the
        # primary instance.
        if options.contains("ibus") == True:
            LOG_MSG.info("Options: started by ibus")
            options.remove("ibus")
            self.__exec_by_ibus=True

        if options.contains("daemonize") == True:
            LOG_MSG.info("Options: daemonize request")
            options.remove("daemonize")
            self.__daemonize=True

        if options.contains("debug") == True:
            LOG_MSG.info("Options: debugging output")
            options.remove("debug")
            LOG_MSG.setLevel(logging.DEBUG)

        # Let the default handler carry on
        return -1

    def do_startup(self):
        # Note : this is called ONLY if we are the primary and sole instance
        LOG_MSG.info("startup")

        # Is it the right way to chain up?
        Gio.Application.do_startup(self)

    def do_command_line(self, args):
        already_running=args.get_is_remote()
        LOG_MSG.info("Remote options parsing %s", already_running)

        options = args.get_options_dict()

        if options.contains("ibus") == True:
            LOG_MSG.info("Remote option: started by ibus - ignored - should not happen")

        if options.contains("daemonize") == True:
            LOG_MSG.info("Remote option: Daemonize - ignored - should not happen")

        if options.contains("debug") == True:
            LOG_MSG.info("Remote option: Debug - ignored - should not happen")

        # Should we chain it? Can't hurt
        Gio.Application.do_command_line(self, args)

        if already_running == False:
            self.activate()

        return 0

    def do_activate(self):
        if self.__bus != None:
            LOG_MSG.info("already activated")
            return

        LOG_MSG.info("activated (%s/%s)", self.get_is_remote(), locale.getlocale())

        if self.__daemonize == True:
            if os.fork():
                sys.exit()

        # Just call the function to initialize it and preload engine if need be
        stt_gst_factory_default()

        # Called only when we are the primary instance
        IBus.init()
        self.__bus = IBus.Bus()
        self.__bus.connect("disconnected", self.__bus_disconnected_cb)

        self.__factory = IBus.Factory.new(self.__bus.get_connection())
        self.__factory.add_engine("stt", GObject.type_from_name("STTEngine"))

        if self.__exec_by_ibus:
            self.__bus.request_name(stt_utils_get_ibus_name(), 0)
        else:
            xml_path=stt_utils_ibus_component_description_path()
            self.__component = IBus.Component.new_from_file(xml_path)
            self.__bus.register_component (self.__component)

        # Start a loop
        self.hold()

    def __bus_disconnected_cb(self, bus):
        LOG_MSG.info("bus disconnect")
        self.release()

if __name__ == "__main__":
    LOG_MSG=logging.getLogger()
    msg_handler=logging.StreamHandler()
    msg_formatter=logging.Formatter('%(levelname)s: \t'
                                    '%(filename)s:%(lineno)d:%(funcName)s: \t'
                                    '%(message)s')
    msg_handler.setFormatter(msg_formatter)
    LOG_MSG.addHandler(msg_handler)
    LOG_MSG.setLevel(logging.INFO)

    # I don't know why, but we need this to internationalize the engine
    import gettext
    gettext.bindtextdomain('ibus-stt')
    gettext.textdomain('ibus-stt')
    locale.bindtextdomain('ibus-stt', None)
    locale.textdomain('ibus-stt')

    app = IMApplication()

    Gst.init(sys.argv)

    # This is for debugging threads
    #from hanging_threads import start_monitoring
    #start_monitoring(seconds_frozen=2, test_interval=100)

    app.add_main_option("ibus",
                        ord("i"),
                        GLib.OptionFlags.NONE,
                        GLib.OptionArg.NONE,
                        _("Executed by IBus"),
                        None,
        )
    app.add_main_option("daemonize",
                        ord("d"),
                        GLib.OptionFlags.NONE,
                        GLib.OptionArg.NONE,
                        _("Daemonize"),
                        None,
        )
    app.add_main_option("debug",
                        ord("g"),
                        GLib.OptionFlags.NONE,
                        GLib.OptionArg.NONE,
                        _("Debug"),
                        None,
        )
    return_value=app.run(sys.argv)
    sys.exit(return_value)
