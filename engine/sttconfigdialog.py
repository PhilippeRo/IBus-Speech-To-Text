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
import locale

from gettext import gettext as _

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Gio, Adw

from sttutils import *
from sttlocalerow import STTLocaleRow
from sttshortcutrow import STTShortcutRow
from sttshortcutdialog import STTShortcutDialog

from sttcurrentlocale import stt_current_locale
from sttvoskmodelmanagers import stt_vosk_online_model_manager

from sttgstvosk import STTGstVosk
from sttgsthandler import STTGstHandler

LOG_MSG=logging.getLogger()

@Gtk.Template(resource_path="/org/freedesktop/ibus/engine/stt/config/sttconfigdialog.ui")
class STTConfigDialog (Adw.PreferencesWindow):
    __gtype_name__="STTConfigDialog"

    localelistbox=Gtk.Template.Child()

    default_locale_switch=Gtk.Template.Child()
    preload_model_switch=Gtk.Template.Child()
    active_on_start_switch=Gtk.Template.Child()

    cancel_button=Gtk.Template.Child()

    commandslistbox=Gtk.Template.Child()
    caselistbox=Gtk.Template.Child()
    diacriticslistbox=Gtk.Template.Child()
    punctuationlistbox=Gtk.Template.Child()
    customlistbox=Gtk.Template.Child()

    commands_row=Gtk.Template.Child()
    case_row=Gtk.Template.Child()
    diacritics_row=Gtk.Template.Child()
    punctuation_row=Gtk.Template.Child()

    categorypage=Gtk.Template.Child()
    category_stack=Gtk.Template.Child()

    commandspage=Gtk.Template.Child()
    casepage=Gtk.Template.Child()
    diacriticspage=Gtk.Template.Child()
    punctuationpage=Gtk.Template.Child()
    custompage=Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._valid_formatting_file_path=False
        self._valid_formatting_file=False
        self._valid_override_file=False

        self._settings=Gio.Settings.new("org.freedesktop.ibus.engine.stt")
        self._settings.bind("preload", self.preload_model_switch, "active", Gio.SettingsBindFlags.DEFAULT)
        self._settings.bind("active-on-start", self.active_on_start_switch, "active", Gio.SettingsBindFlags.DEFAULT)

        self._locales = {}
        self._values_dict={}
        self._utterances_dict={}
        self._no_model_toast=None
        self._unsupported_locale_toast=None

        # Make sure it is initialized before what follows
        stt_vosk_online_model_manager()

        # Load current locale
        self._current_locale = stt_current_locale()
        self._locale_sig_id=self._current_locale.connect("changed", self._locale_changed_cb)
        self._override_file_changed_id=self._current_locale.connect("override-file-changed", self._override_file_changed_cb)
        self._override_file_written=False

        # Add system locale first (even if it's not a supported locale).
        system_locale=locale.getlocale()[0]
        self._add_locale_row(system_locale)

        # If current locale is not system locale, add it then.
        if system_locale != self._current_locale.locale:
            self._add_locale_row(self._current_locale.locale)

        # Load all available locales
        supported_locales=stt_vosk_online_model_manager().supported_locales()
        supported_locales.sort()

        for locale_str in supported_locales:
            # Check we are not loading the current locale twice
            if locale_str in [self._current_locale.locale, system_locale]:
                continue

            LOG_MSG.debug("loading %s", locale_str)
            self._add_locale_row(locale_str)

        # This updates _valid_formatting_file and _valid_override_file
        self._load_utterances()

        # This is to force some preloading for the recognition engine whatever
        # the settings for "preloading" or "active-on-start"
        self._engine = STTGstHandler()

        pipeline=STTGstVosk(current_locale=self._current_locale)
        self._engine.connect("model-changed", self._engine_model_changed_cb)

        self._engine.set_pipeline(pipeline)
        pipeline.preload()

        LOG_MSG.debug("model exists %s", self._engine.has_model())

        # Update sensitivity and such
        if self.default_locale_switch.get_active() != self._current_locale.default_locale:
            self.default_locale_switch.set_active(self._current_locale.default_locale)

        self._set_locale_rows_sensitivity()

        if self._engine.has_model() == False:
            self._engine_has_no_model()

        if self._valid_formatting_file == False:
            self._unsupported_locale()

        self._toast_action=Gio.SimpleAction.new("manage_model", None)
        action_group=Gio.SimpleActionGroup.new()
        action_group.insert(self._toast_action)
        self.insert_action_group("toast", action_group)
        self._toast_action.connect("activate", self._manage_model_action_activated)

    def _set_locale_rows_sensitivity(self):
        for row in self._locales.values():
            if row.check_button.get_active() == True:
                row.set_sensitive(True)
            else:
                row.set_sensitive(not self._current_locale.default_locale)

    def _add_locale_row(self, locale_str):
        if len(self._locales) == 0:
            row = STTLocaleRow(current_locale=self._current_locale, locale_str=locale_str, radio_group=None)
        elif self._locales.get(locale_str, None) != None:
            LOG_MSG.error("the locale is already included (%s)", locale_str)
            return
        else:
            # Get first row of the group to associate it
            # Note: we cannot rely on the fact there is at least one row
            row = next(iter(self._locales.items()))[1]
            row = STTLocaleRow(current_locale=self._current_locale, locale_str=locale_str, radio_group=row.check_button)

        self.localelistbox.add(row)
        self._locales[locale_str]=row

    def _empty_shortcut_page(self):
        self._valid_formatting_file_path=False
        self._valid_formatting_file=False
        self._valid_override_file=False

        # Empty all utterances listboxes
        for row in self._values_dict.values():
            listbox=row.pref_group
            listbox.remove(row)

        self.commands_row.set_visible(False)
        self.case_row.set_visible(False)
        self.diacritics_row.set_visible(False)
        self.punctuation_row.set_visible(False)

        self._values_dict={}
        self._utterances_dict={}

    def _load_current_locale(self):
        # Make sure locale exists
        row = self._locales.get(self._current_locale.locale, None)
        if row == None:
            # Current locale is not in the list (and is probably not supported)
            self._add_locale_row(self._current_locale.locale)

        self._empty_shortcut_page()
        self._load_utterances()

        # This toast has precedence over the next
        if self._engine.has_model() == False:
            self._engine_has_no_model()
            return

        if self._no_model_toast != None:
            self._no_model_toast.dismiss()
            self._no_model_toast = None

        if self._valid_formatting_file == False:
            self._unsupported_locale()
        elif self._unsupported_locale_toast != None:
            self._unsupported_locale_toast.dismiss()
            self._unsupported_locale_toast = None

    def _locale_changed_cb(self, current_locale):
        if self.default_locale_switch.get_active() != self._current_locale.default_locale:
            self.default_locale_switch.set_active(self._current_locale.default_locale)

        self._set_locale_rows_sensitivity()

        # Try to load formatting file
        self._load_current_locale()

    def _override_file_changed_cb(self, current_locale, deleted):
        if deleted == False and self._override_file_written == False:
            LOG_MSG.debug("override file changed")
            self._load_current_locale()

        self._override_file_written=False

    def _error_dialog_response_cb(self, dialog, response):
        dialog.destroy()

    def open_locale_file_cb(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            dialog.destroy()
            return

        file=dialog.get_file()
        dialog.destroy()
        self._current_locale.formatting_file_path(file.get_path())

    @Gtk.Template.Callback()
    def default_locale_switched_cb(self, switch, value):
        if switch.get_active() == True:
            self._current_locale.locale="None"
        else: # Set the current one
            self._current_locale.locale=self._current_locale.locale

        self._set_locale_rows_sensitivity()

    @Gtk.Template.Callback()
    def new_formatting_file_button_clicked_cb(self, button):
        dialog=Gtk.FileChooserDialog(transient_for=self, title=_("Open Formatting File"), modal=True, action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(_("Cancel"), Gtk.ResponseType.CANCEL, _("Open"), Gtk.ResponseType.ACCEPT)
        dialog.connect("response", self.open_locale_file_cb)
        dialog.set_transient_for(self)
        dialog.present()

    @Gtk.Template.Callback()
    def commands_row_activated_cb(self, row):
        self.present_subpage(self.categorypage)
        self.category_stack.set_visible_child(self.commandspage)

    @Gtk.Template.Callback()
    def case_row_activated_cb(self, row):
        self.present_subpage(self.categorypage)
        self.category_stack.set_visible_child(self.casepage)

    @Gtk.Template.Callback()
    def diacritics_row_activated_cb(self, row):
        self.present_subpage(self.categorypage)
        self.category_stack.set_visible_child(self.diacriticspage)

    @Gtk.Template.Callback()
    def punctuation_row_activated_cb(self, row):
        self.present_subpage(self.categorypage)
        self.category_stack.set_visible_child(self.punctuationpage)

    @Gtk.Template.Callback()
    def custom_row_activated_cb(self, row):
        self.present_subpage(self.categorypage)
        self.category_stack.set_visible_child(self.custompage)

    @Gtk.Template.Callback()
    def cancel_button_clicked_cb(self, button):
        self.close_subpage()

    def _apply_change(self):
        LOG_MSG.debug("override file being written")
        self._override_file_written=True

        json_data={}
        command_values=[]
        json_data["commands"]=command_values
        case_values=[]
        json_data["case"]=case_values
        diacritics_values=[]
        json_data["diacritics"]=diacritics_values
        punctuation_values=[]
        json_data["punctuation"]=punctuation_values
        custom_values=[]
        json_data["custom"]=custom_values

        write_changes=False
        for row in self._values_dict.values():
            value=row.get_json_data()
            if value == None:
                continue

            write_changes=True
            if row.pref_group == self.commandslistbox:
                command_values.append(value)
            elif row.pref_group == self.caselistbox:
                case_values.append(value)
            elif row.pref_group == self.diacriticslistbox:
                diacritics_values.append(value)
            elif row.pref_group == self.punctuationlistbox:
                punctuation_values.append(value)
            elif row.pref_group == self.customlistbox:
                custom_values.append(value)

        if write_changes == True:
            self._current_locale.overriding=json_data

    def shortcut_row_reset_cb(self, row):
        # After a row is reset remove extra utterances from global dictionary
        for utterance in row._extra_utterances:
            self._utterances_dict.pop(utterance)

        self._apply_change()

    def shortcut_row_deleted_cb(self, row):
        self._values_dict.pop(row.value)
        for utterance in row.utterances:
            self._utterances_dict.pop(utterance)
        for utterance in row._extra_utterances:
            self._utterances_dict.pop(utterance)

        parent = row.get_parent()
        parent.remove(row)

        self._apply_change()

    def shortcut_dialog_response_cb(self, dialog, response):
        if response == Gtk.ResponseType.APPLY:
            # Modification
            (added_utterances, removed_utterances)=dialog.apply_to_row()
            for utterance in added_utterances:
                self._utterances_dict[utterance] = True
            for utterance in removed_utterances:
                self._utterances_dict.pop(utterance)

            self._apply_change()
        elif response == Gtk.ResponseType.OK:
            # Addition
            row = dialog.get_new_row()
            row.pref_group=self.customlistbox
            self.customlistbox.add(row)
            row.connect("activated", self.shortcut_row_activated_cb)
            row.connect("delete", self.shortcut_row_deleted_cb)
            row.connect("reset", self.shortcut_row_reset_cb)

            # It can't be a diacritic sign as the shortcut was created
            self._values_dict[row.value]=row

            # Only _extra_utterances can be added
            for utterance in row._extra_utterances:
                self._utterances_dict[utterance] = True

            self._apply_change()

        dialog.destroy()

    def present_shortcut_dialog(self, row):
        dialog = STTShortcutDialog(row=row, engine=self._engine, transient_for=self)
        dialog.connect("response", self.shortcut_dialog_response_cb)
        dialog.present()

    def shortcut_row_activated_cb(self, row):
        self.present_shortcut_dialog(row)

    @Gtk.Template.Callback()
    def new_shortcut_clicked_cb(self, button):
        self.present_shortcut_dialog(None)

    def _load_section(self, json_data, section, listbox, cat_row):
        item_list=json_data.get(section)
        if item_list  in (None,[]):
            if cat_row != None:
                cat_row.set_visible(False)
            return

        if cat_row != None:
            cat_row.set_visible(True)

        for item in item_list:
            value=item.get("value")
            # It may happen with diacritics that it's a list
            # The [0] is the non combining unicode (ie U+005E for circumflex)
            # and [1] is the combining unicode character (ie U+0302 for circumflex)

            utterances=item.get("utterances")
            description=item.get("description")

            # In case there is only one
            if isinstance(utterances,str):
                utterances = [utterances]

            # Each occurrence has to be unique
            for utterance in utterances[:]:
                existing_row = self._utterances_dict.get(utterance, False)
                if existing_row == True:
                    LOG_MSG.error("utterance already exists (%s)", utterance)
                    utterances.remove(utterance)
                    continue

                self._utterances_dict[utterance] = True

            if isinstance(value,list):
                row=self._values_dict.get(value[0], None)
            else:
                row=self._values_dict.get(value, None)

            if row == None:
                if utterances == []:
                    continue

                row=STTShortcutRow(value=value,
                                   utterances=utterances,
                                   description=description,
                                   editable=False,
                                   pref_group=listbox)
                listbox.add(row)
                row.connect("activated", self.shortcut_row_activated_cb)
                row.connect("reset", self.shortcut_row_reset_cb)

                if isinstance(value, list):
                    self._values_dict[value[0]]=row
                else:
                    self._values_dict[value]=row
            else:
                row.utterances=list(set(row.utterances)|set(utterances))
                row.description=description

    def _load_formatting_file(self):
        LOG_MSG.debug("loading formatting file")
        json_data=self._current_locale.formatting
        if json_data == None:
            return

        # Sections must be loaded in the same order as in the utterance tree
        # FIXME! should we should some categories necessary (command) ?
        self._load_section(json_data, "commands", self.commandslistbox, self.commands_row)
        self._load_section(json_data, "case", self.caselistbox, self.case_row)
        self._load_section(json_data, "diacritics", self.diacriticslistbox, self.diacritics_row)
        self._load_section(json_data, "punctuation", self.punctuationlistbox, self.punctuation_row)
        self._load_section(json_data, "custom", self.customlistbox, None)

        self._valid_formatting_file=True

    def _load_section_override(self, item_list, listbox):
        if item_list == None:
            return

        for item in item_list:
            value=item.get("value")
            # It may happen with diacritics that it's a list
            # The [0] is the non combining unicode (ie U+005E for circumflex)
            # and [1] is the combining unicode character (ie U+0302 for circumflex)

            utterances=item.get("utterances")
            description=item.get("description")

            if utterances not in (None,[]):
                # In case there is only one
                if isinstance(utterances, str):
                    utterances = [utterances]

                # Each occurrence has to be unique
                for utterance in utterances[:]:
                    existing_row = self._utterances_dict.get(utterance, False)
                    if existing_row == True:
                        LOG_MSG.error("utterance already exists (%s)", utterance)
                        utterances.remove(utterance)
                        continue

                    self._utterances_dict[utterance] = True

            # See if a row with same value already exists.
            # Check in all the listbox
            if isinstance(value,list):
                row=self._values_dict.get(value[0], None)
            else:
                row=self._values_dict.get(value, None)

            if row != None:
                if description != None:
                    row.description = description

                if utterances not in (None,[]):
                    row.add_extra_utterances(utterances)
            elif utterances not in (None,[]):
                row=STTShortcutRow(value=value,
                                   extra_utterances=utterances,
                                   description=description,
                                   editable=True,
                                   pref_group=listbox)
                listbox.add(row)
                row.connect("delete", self.shortcut_row_deleted_cb)
                row.connect("reset", self.shortcut_row_reset_cb)
                row.connect("activated", self.shortcut_row_activated_cb)
                if isinstance(value, list):
                    self._values_dict[value[0]]=row
                else:
                    self._values_dict[value]=row

    def _load_overriding_file(self):
        # Load custom formatting file as well. Note: it overrides existing keys
        LOG_MSG.debug("loading overriding file")
        json_data=self._current_locale.overriding
        if json_data == None:
            return

        # Now add overrides
        self._load_section_override(json_data.get("commands"), self.commandslistbox)
        self._load_section_override(json_data.get("case"), self.caselistbox)
        self._load_section_override(json_data.get("diacritics"), self.diacriticslistbox)
        self._load_section_override(json_data.get("punctuation"), self.punctuationlistbox)
        self._load_section_override(json_data.get("custom"), self.customlistbox)

        self._valid_override_file=True

    def _load_utterances(self):
        self._load_formatting_file()
        if self._valid_formatting_file == False:
            self._empty_shortcut_page()

        self._load_overriding_file()

    def _manage_model_action_activated(self, action, param):
        # Get row for current locale
        row = self._locales.get(self._current_locale.locale, None)
        row.manage_model()

    def _toast_dismissed(self, toast):
        if toast == self._no_model_toast:
            self._no_model_toast=None

            # Display the other message if needed
            if self._valid_formatting_file == False:
                self._unsupported_locale()
        else:
            self._unsupported_locale_toast=None

    def _unsupported_locale(self):
        # Careful: we can have no formatting file but an overriding one !!
        if self._no_model_toast != None:
            return

        if self._unsupported_locale_toast != None:
            return

        if self._valid_formatting_file_path == True:
            self._unsupported_locale_toast=Adw.Toast(title=_("The file that defines automatic formatting for your locale does not have the proper format."), timeout=0)
        else:
            self._unsupported_locale_toast=Adw.Toast(title=_("A file that defines automatic formatting for your locale is missing. You can manually add one."), timeout=0)

        self._unsupported_locale_toast.connect("dismissed", self._toast_dismissed)
        self.add_toast(self._unsupported_locale_toast)

    def _engine_has_no_model(self):
        if self._no_model_toast != None:
            return

        if self._unsupported_locale_toast != None:
            self._unsupported_locale_toast.dismiss()
            self._unsupported_locale_toast = None

        self._no_model_toast=Adw.Toast(title=_("There is no available model for the current locale"), timeout=0, button_label=_("Download Model"), action_name="toast.manage_model")
        self._no_model_toast.connect("dismissed", self._toast_dismissed)
        self.add_toast(self._no_model_toast)

    def _engine_model_changed_cb(self, engine):
        if engine.has_model() == False:
            self._engine_has_no_model()
        elif self._no_model_toast != None:
            self._no_model_toast.dismiss()
            self._no_model_toast = None
