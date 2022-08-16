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
import subprocess
import logging

from gettext import gettext as _

import gi

gi.require_version('IBus', '1.0')
gi.require_version('Pango', '1.0')
gi.require_version('Gtk', '4.0')

from gi.repository import IBus
from gi.repository import Gtk
from gi.repository import Gio

from sttutils import *
from sttgstfactory import stt_gst_factory_default
from sttsegmentprocess import STTSegmentProcess, STTParseModes

LOG_MSG=logging.getLogger()

class STTEngine(IBus.Engine):
    __gtype_name__ = 'STTEngine'

    def __init__(self):
        super().__init__()

        LOG_MSG.info("STTEngine created %s", self)

        self._text_processor=STTSegmentProcess()
        self._text_processor.connect("mode-changed", self._mode_changed)

        self._left_text=""
        self._left_text_reset=True

        self._preediting=False

        self._settings=Gio.Settings.new("org.freedesktop.ibus.engine.stt")
        self._settings.connect("changed::stop-on-keypress", self._stop_on_key_pressed_changed)
        self._stop_on_key_pressed=False
        self._update_stop_on_key_pressed()

        self._settings.connect("changed::preedit-text", self._on_preedit_text_changed)
        self._settings.connect("changed::format-preedit", self._on_format_preedit_changed)
        self._preedit_text=self._settings.get_boolean("preedit-text")
        self._format_preedit=self._settings.get_boolean("format-preedit")
        self._partial_text_id=0

        self.__prop_list=IBus.PropList()
        self.__prop_list.append(IBus.Property(key="toggle-recording",
                                              label=_("Recognition off"),
                                              icon="audio-input-microphone",
                                              type=IBus.PropType.TOGGLE,
                                              state=IBus.PropState.UNCHECKED,
                                              tooltip=_("Toggle speech recognition")))

        menu_prop_list = IBus.PropList()
        menu_prop_list.append(IBus.Property(key="dictation-mode",
                                            label=_("Dictate"),
                                            type=IBus.PropType.RADIO,
                                            state=IBus.PropState.CHECKED,
                                            tooltip=_("Toggle dictation mode")))
        menu_prop_list.append(IBus.Property(key="literal-mode",
                                            label=_("Dictate (no formatting)"),
                                            type=IBus.PropType.RADIO,
                                            state=IBus.PropState.UNCHECKED,
                                            tooltip=_("Toggle dictation mode with no automatic formatting")))
        menu_prop_list.append(IBus.Property(key="spelling-mode",
                                            label=_("Spell"),
                                            type=IBus.PropType.RADIO,
                                            state=IBus.PropState.UNCHECKED,
                                            tooltip=_("Toggle spelling mode")))
        self.__prop_list.append(IBus.Property(key="mode-menu",
                                              label=_("Recognition mode"),
                                              icon=None,
                                              type=IBus.PropType.MENU,
                                              sensitive=False,
                                              sub_props=menu_prop_list))

        self.__prop_list.append(IBus.Property(key="digit-mode",
                                              label=_("Use digits"),
                                              type=IBus.PropType.TOGGLE,
                                              state=IBus.PropState.UNCHECKED,
                                              sensitive=False,
                                              tooltip=_("Toggle the use of digits")))

        self.__prop_list.append(IBus.Property(key="configuration",
                                              label=_("Settings"),
                                              type=IBus.PropType.NORMAL,
                                              sensitive=True,
                                              tooltip=_("Configure IBus STT")))
        self.__prop_list.append(IBus.Property(key="about",
                                              label=_("About IBus Speech To Text"),
                                              type=IBus.PropType.NORMAL,
                                              sensitive=True,
                                              tooltip=_("Learn more about IBus STT")))

        self._engine_connected=False
        self._engine=stt_gst_factory_default().new_handler()
        if self._engine.has_model() == False:
            LOG_MSG.error("engine has no valid model")

    def __del__(self):
        LOG_MSG.info("STTEngine destroyed %s", self)

    def _disconnect_from_engine(self):
        if self._engine_connected == False:
            LOG_MSG.debug("not connected to engine %s", self)
            return

        LOG_MSG.info("disconnect from engine %s", self)
        self._engine.disconnect_by_func(self._model_changed)
        self._engine.disconnect_by_func(self._state_changed)
        self._engine.disconnect_by_func(self._got_text)

        if self._partial_text_id != 0:
            self._engine.disconnect(self._partial_text_id)
            self._partial_text_id=0

        self._engine_connected=False

    def _connect_to_engine(self):
        if self._engine_connected == True:
            LOG_MSG.debug("already connected to engine %s", self)
            return

        LOG_MSG.debug("connect to engine %s", self)
        self._engine.connect("model-changed", self._model_changed)
        self._engine.connect("state", self._state_changed)
        self._engine.connect("text", self._got_text)

        if self._preedit_text == True:
            self._partial_text_id=self._engine.connect("partial-text", self._got_partial_text)

        self._engine_connected=True

    def do_destroy (self):
        # This method is inherited from IBusObject
        LOG_MSG.info("STTEngine destruction %s", self)

        self._settings.disconnect_by_func(self._stop_on_key_pressed_changed)
        self._settings=None

        self._text_processor.disconnect_by_func(self._mode_changed)
        self._text_processor=None

        # we need to do that since _engine might live on if preloaded
        self._disconnect_from_engine()
        self._engine.destroy()
        self._engine = None

        # This function needs CHAINING and this way or it leaks
        IBus.Engine.do_destroy(self)

    def _update_stop_on_key_pressed(self):
        self._stop_on_key_pressed=self._settings.get_boolean("stop-on-keypress")

    def _stop_on_key_pressed_changed(self, settings, key):
        self._update_stop_on_key_pressed()

    def _update_preedit_text(self):
        self._preedit_text=self._settings.get_boolean("preedit-text")
        if self._partial_text_id != 0:
            if self._preedit_text == True:
                return

            self._engine.disconnect(self._partial_text_id)
            self._partial_text_id=0
        elif self._preedit_text == True:
            self._partial_text_id=self._engine.connect("partial-text", self._got_partial_text)

    def _on_preedit_text_changed(self, settings, key):
        self._update_preedit_text()

    def _on_format_preedit_changed(self, settings, key):
        self._format_preedit=self._settings.get_boolean("format-preedit")

    def _update_state(self):
        if self._engine.is_running() == True:
            button_state=IBus.PropState.CHECKED
            button_label=IBus.Text(_("Recognition on"))
        else:
            button_state=IBus.PropState.UNCHECKED
            button_label=IBus.Text(_("Recognition off"))

        is_dictation = bool(self._text_processor.mode == STTParseModes.DICTATION)
        is_spelling = bool(self._text_processor.mode == STTParseModes.SPELLING)
        is_literal = bool(self._text_processor.mode == STTParseModes.LITERAL)

        prop=IBus.Property(key="toggle-recording",
                           label=button_label,
                           icon="audio-input-microphone",
                           type=IBus.PropType.TOGGLE,
                           state=button_state,
                           sensitive=self._engine.has_model(),
                           tooltip=_("Toggle speech recognition"))
        self.update_property(prop)

        prop = IBus.Property(key="mode-menu",
                             label=_("Recognition modes"),
                             icon=None,
                             type=IBus.PropType.MENU,
                             sensitive=(button_state == IBus.PropState.CHECKED))
        self.update_property(prop)

        prop=IBus.Property(key="dictation-mode",
                           label=_("Dictate"),
                           type=IBus.PropType.RADIO,
                           state=IBus.PropState.CHECKED if is_dictation else IBus.PropState.UNCHECKED,
                           sensitive=self._text_processor.can_dictate,
                           tooltip=_("Toggle dictation mode"))
        self.update_property(prop)

        prop=IBus.Property(key="literal-mode",
                           label=_("Dictate (no formatting)"),
                           type=IBus.PropType.RADIO,
                           state=IBus.PropState.CHECKED if is_literal else IBus.PropState.UNCHECKED,
                           tooltip=_("Toggle dictation mode with no automatic formatting"))
        self.update_property(prop)

        prop=IBus.Property(key="spelling-mode",
                           label=_("Spell"),
                           type=IBus.PropType.RADIO,
                           state=IBus.PropState.CHECKED if is_spelling else IBus.PropState.UNCHECKED,
                           sensitive=self._text_processor.can_spell,
                           tooltip=_("Toggle spelling mode"))
        self.update_property(prop)

        use_digits = self._text_processor.use_digits
        prop=IBus.Property(key="digit-mode",
                           label=_("Use digits"),
                           type=IBus.PropType.TOGGLE,
                           state=IBus.PropState.CHECKED if use_digits else IBus.PropState.UNCHECKED,
                           sensitive=self._text_processor.can_use_digits,
                           tooltip=_("Toggle the use of digits"))
        self.update_property(prop)

    def _state_changed(self, engine):
        self._update_state()

    def _model_changed(self, engine):
        LOG_MSG.debug("engine model has changed")
        if self._engine.has_model() == False:
            LOG_MSG.error("engine has no model")

        self._update_state()

    def _mode_changed(self, text_processor):
        self._update_state()

    def do_enable(self):
        LOG_MSG.info('enable %s', self)

        # Necessary to indicate we'll use surrounding text
        (ibus_text, cursor_pos, anchor_pos)=self.get_surrounding_text()
        self._set_left_text(ibus_text, cursor_pos)

        self._connect_to_engine()
        if self._engine.has_model() == False:
            # There is something wrong with our model, display config dialog
            subprocess.Popen([os.path.join(stt_utils_get_libexec(), "ibus-setup-stt")])
            return

        active_on_start = self._settings.get_boolean("active-on-start")
        LOG_MSG.info("engine enabled %s (active_on_start=%s)", self, active_on_start)
        if active_on_start == True:
            self._engine.run()
            self._update_state()

    def do_disable(self):
        LOG_MSG.info('disable %s', self)
        self._engine.stop()
        self._disconnect_from_engine()

    def do_focus_in(self):
        LOG_MSG.debug("focus in")
        self.register_properties(self.__prop_list)
        self._update_state()

    def do_focus_out(self):
        LOG_MSG.debug("focus out")
        self._reset()

    def do_reset(self):
        LOG_MSG.debug("do reset")
        self._reset()

    def do_property_activate(self, prop_name, state):
        # Make sure that we are not in the middle of an analysis.
        # If we changed the mode during analysis it would affect the next
        # analysis (partial or not) and make it wrong.
        if self._text_processor.is_processing() == True:
            self._engine.get_final_results()

        if prop_name == 'toggle-recording':
            if bool(state) == True:
                self._engine.run()
            else:
                self._engine.stop()
        elif prop_name == 'dictation-mode':
            if state == True:
                self._text_processor.mode = STTParseModes.DICTATION
        elif prop_name == 'spelling-mode':
            if state == True:
                self._text_processor.mode = STTParseModes.SPELLING
        elif prop_name == 'literal-mode':
            if state == True:
                self._text_processor.mode = STTParseModes.LITERAL
        elif prop_name == 'digit-mode':
            self._text_processor.use_digits = bool(state)
        elif prop_name == 'configuration':
            subprocess.Popen([os.path.join(stt_utils_get_libexec(), "ibus-setup-stt")])
        elif prop_name == 'about':
            dialog = Gtk.AboutDialog(program_name=_("IBus Speech To Text"),
                            title=_("About IBus Speech To Text"),
                            logo_icon_name="user-available-symbolic",
                            version=stt_utils_get_version(),
                            copyright="Copyright © 2022 Philippe Rouquier",
                            comments=_("What you say is always write."),
                            website="https://github.com/PhilippeRo/ibus-stt",
                            license_type=Gtk.License.GPL_3_0,
                            translator_credits=_("translator-credits"))
            dialog.present()

        self._update_state()

    def _got_partial_text(self, engine, utterance):
        if (self.client_capabilities & IBus.Capabilite.PREEDIT_TEXT) == 0:
            LOG_MSG.debug("client has no Preedit capability")
            return

        if self._format_preedit == True:
            utterance = self._text_processor.utterance_process_begin(utterance, self._left_text)

        # Problem here is that we cannot perform any cancellation while we are
        # in the middle of an analysis or it could be repeated the next time
        # we perform another analysis of another partial utterance.
        # So we finalize first then get on with the deletion to avoid its
        # repetition.
        # Note: it does not matter that pending_cancel_size is reset to 0
        if self._text_processor.pending_cancel_size == 0:
            # Note: we accept "" (in case we need to remove previous partial text)
            ibus_text=IBus.Text.new_from_string(utterance)
            self.update_preedit_text_with_mode(ibus_text,
                                               0,
                                               True,
                                               IBus.PreeditFocusMode.CLEAR)
            self._preediting=True
        else:
            self._engine.get_final_results()

    def _got_text(self, engine, utterance):
        text = self._text_processor.utterance_process_end(utterance, self._left_text)
        if self._preediting == True:
            # Don't call this if there was no preediting before
            self.update_preedit_text_with_mode(IBus.Text.new_from_string(""),
                                               0,
                                               True,
                                               IBus.PreeditFocusMode.CLEAR)
            self._preediting=False

        # Handle potential pending cancellations
        # Note: once accessed pending_cancel_size is reset to 0
        cancel_length = self._text_processor.pending_cancel_size
        if cancel_length != 0:
            if (self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT) == 0:
                LOG_MSG.debug("client application has no surrounding text capability")

            self.delete_surrounding_text(-cancel_length, cancel_length)

            # Keep our left text updated
            text_len=len(self._left_text)
            text_len=text_len-cancel_length if cancel_length <= text_len else text_len
            self._left_text=self._left_text[:text_len]

        # Note : there could be text to write even after cancellation ("cancel
        # write this").
        if text != "":
            self.commit_text(IBus.Text.new_from_string(text))
            self._left_text+=text
            self._left_text_reset=False
            LOG_MSG.debug("current left text (after commit) (%s)", self._left_text)

    def _reset(self):
        if self._engine.is_running():
            self._engine.get_final_results()

        self._text_processor.reset()
        self._left_text=""
        self._left_text_reset=True
        # Note: we used to do this in the hope it would force update but there
        # is a potential problem here: select text and click -> the selected
        # text is deleted !!
        # if self._engine.is_running() == True:
        #     self.commit_text(IBus.Text.new_from_string(""))

    def do_process_key_event(self, keyval, keycode, state):
        if (state & IBus.ModifierType.RELEASE_MASK) != 0:
            if self._stop_on_key_pressed == True:
                self._engine.stop()
                self._update_state()
        else:
            # Any keystroke should stop a potential ongoing processing
            if self._text_processor.is_processing() == True:
                self._engine.get_final_results()

            # Usually there is a "set-surrounding-text" event after a key press.
            # So get ready for the update (though we keep our current one if
            # none comes). This is in case the key press is an arrow that moved
            # the cursor. Instead of tracking this kind of strokes, let IBus
            # tell us how the surrounding text changed.
            self._left_text_reset = True

        # Let the keystroke be propagated
        return False

    def _set_left_text(self, ibus_text, cursor_pos):
        # Each text commit or preedit may reliably (but not always for example
        # gtk3 and gtk4) sets the surrounding text. Problem is, preedit text
        # is included.
        text_bytes=ibus_text.get_text().encode()
        self._left_text=text_bytes[:cursor_pos].decode("utf-8")
        LOG_MSG.debug("set left text (%s) (cursor pos=%i)", self._left_text, cursor_pos)

        # Reminder we do not care about the context on the right, it is up to
        # the user to add a potential missing whitespace.

    def do_set_surrounding_text(self, ibus_text, cursor_pos, anchor_pos):
        LOG_MSG.debug("left text changed (%s) (cursor pos=%i, anchor_pos=%i)",
                      ibus_text.get_text(), cursor_pos, anchor_pos)

        if self._left_text_reset == True:
            self._set_left_text(ibus_text, cursor_pos)

        # We need to chain this function if we want get_surrounding_text to work
        IBus.Engine.do_set_surrounding_text(self, ibus_text, cursor_pos, anchor_pos)
