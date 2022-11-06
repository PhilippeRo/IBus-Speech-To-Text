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

from enum import IntFlag

from gi.repository import GObject

from sttcurrentlocale import STTCurrentLocale, stt_current_locale

LOG_MSG=logging.getLogger()

class STTParseModes(IntFlag):
    NONE      = 0
    DICTATION = 1
    SPELLING  = 2
    LITERAL   = 4
    ALL       = DICTATION|SPELLING|LITERAL

class STTCase(IntFlag):
    NONE     = 0
    LOWER    = 1
    UPPER    = 2
    CAPITAL  = 4
    LOCK     = 8

    LOCK_UPPER = LOCK|UPPER
    LOCK_CAPITAL = LOCK|CAPITAL

class STTParserInterface():
    def cancel(self):
        self.cancel()
        return True

    def flip_use_digits(self):
        self.flip_use_digits()
        return True

    def set_mode(self, mode):
        self.set_mode(mode)
        return True

    def set_case(self, case):
        self.set_case(case)
        return True

    def add_diacritic(self, diacritic):
        self.add_diacritic(diacritic)
        return True

    # This one is used for both punctuation and custom
    def add_words(self, words):
        self.add_words(words)
        return True

    def add_shortcut(self, words):
        return self.add_shortcut(words)

class STTNodeType (IntFlag):
    NONE            = 0
    OVERRIDDEN      = 1
    COMMAND         = 2
    CASE            = 4
    DIACRITICS      = 8
    PUNCTUATION     = 16
    CUSTOM          = 32

class STTWordNode(dict):
    def __init__(self, depth):
        super().__init__()
        self._callback=None
        self._value=None
        self._depth=depth
        self._modes=STTParseModes.NONE

    def is_match(self, mode):
        if (mode & self._modes) == 0:
            return False
        if self._callback != None or self._value != None:
            return True
        return False

class STTUtteranceTree(GObject.Object):
    __gtype_name__="STTUtteranceTree"
    __gsignals__= {
        "changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, current_locale=None):
        super().__init__()
        if current_locale == None:
            self._current_locale=stt_current_locale()
        else:
            self._current_locale=current_locale

        self._current_locale.connect("changed", self._formatting_file_changed_cb)
        self._current_locale.connect("override-file-changed", self._overriding_file_changed_cb)
        self.reset()

        self._load_formatting_file()
        self._load_overriding_file()

    def _find_node(self, parser, words, word_i, node):
        word = words[word_i]
        node_next = node.get(word)
        if node_next == None:
            # we don't have any other match in tree.
            # Note : value could be None. For example if we have :
            # "it's"/"a"/"beautiful"/"day" in tree (value is associated with "day")
            # and we are searching "it's"/"a"
            # In this case, parent node returns it's value if any. For example,
            # "it's"/"a" may have a value
            if node.is_match(parser.mode) == True:
                return node

            return None

        word_i += 1
        if word_i < len(words):
            # We haven't reached the end of the utterance
            return_node = self._find_node(parser, words, word_i, node_next)
            if return_node != None:
                return return_node

        if node_next.is_match(parser.mode) == True:
            return node_next

        return None

    def parse(self, parser, words, word_i):
        node = self._find_node(parser, words, word_i, self._root)
        if node == None:
            return word_i

        if node._callback == None:
            LOG_MSG.error("node has no callback")
            return word_i

        if node._value != None:
            result=node._callback(parser, node._value)
        else:
            result=node._callback(parser)

        # In case of an error in the callback, pretend there is nothing
        if result == False:
            return word_i

        return word_i + node._depth

    def _add_to_node(self, word_iter, parent, depth):
        depth += 1
        word = next(word_iter, None)
        if word is None:
            # Reached the end.
            return parent

        child=parent.get(word)
        if child == None:
            child = STTWordNode(depth)
            parent[word] = child

        return self._add_to_node(word_iter, child, depth)

    def _add_to_tree(self, utterance):
        words=utterance.split()
        if words == None:
            return None

        word_iter=iter(words)
        return self._add_to_node(word_iter, self._root, 0)

    def _add_utterances_to_tree(self, utterances, callback, value, node_modes):
        if utterances in (None, []):
            LOG_MSG.error("value has not associated utterance(s)")
            return

        for utterance in utterances:
            node = self._add_to_tree(utterance)
            if node == None:
                LOG_MSG.error("no node could be created (%s)", utterance)
                return

            if node._callback != None:
                LOG_MSG.error("node already exists (%s)", utterance)
                continue

            node._callback = callback
            node._value = value
            node._modes = node_modes

    def _load_replacements_list(self, item_list):
        if item_list == None:
            return

        for item in item_list:
            # In case there is only one
            utterances = item.get("utterances")
            if isinstance(utterances,str):
                utterances = [utterances]

            value = item.get("value")
            if value is None:
                value = item.get("shortcut")
                if value is None:
                    LOG_MSG.error("Utterance with no value")
                    return
                self._add_utterances_to_tree(utterances,
                                             STTParserInterface.add_shortcut,
                                             value,
                                             STTParseModes.DICTATION)
            else:
                self._add_utterances_to_tree(utterances,
                                             STTParserInterface.add_words,
                                             value,
                                             STTParseModes.DICTATION)

    def _load_punctuation_list(self, item_list):
        if item_list == None:
            return

        for item in item_list:
            # In case there is only one
            utterances = item.get("utterances")
            if isinstance(utterances,str):
                utterances = [utterances]

            value = item.get("value")
            if value is None:
                LOG_MSG.error("Utterance with no value")
                return

            self._add_utterances_to_tree(utterances,
                                         STTParserInterface.add_words,
                                         value,
                                         STTParseModes.SPELLING |
                                         STTParseModes.DICTATION)

    def _load_diacritics_list(self, item_list):
        if item_list == None:
            return

        for item in item_list:
            value = item.get("value")
            if not isinstance(value, list) or len(value) != 2:
                LOG_MSG.error("Malformed diacritic value (type=%s, num=%i)", type(value), len(value))
                continue

            # In case there is only one
            utterances = item.get("utterances")
            if isinstance(utterances,str):
                utterances = [utterances]

            self._add_utterances_to_tree(utterances, STTParserInterface.add_diacritic, (value[0], value[1]), STTParseModes.SPELLING | STTParseModes.DICTATION)

    def _load_case_list(self, item_list):
        if item_list == None:
            return

        for item in item_list:
            value=item.get("value")
            utterances=item.get("utterances")

            # In case there is only one
            if isinstance(utterances,str):
                utterances = [utterances]

            if value == "upper all":
                callback = STTParserInterface.set_case
                value = STTCase.LOCK_UPPER
            elif value == "upper":
                callback = STTParserInterface.set_case
                value = STTCase.UPPER
            elif value == "lower":
                callback = STTParserInterface.set_case
                value = STTCase.LOWER
            elif value == "title":
                callback = STTParserInterface.set_case
                value = STTCase.LOCK_CAPITAL
            elif value == "capitalize":
                callback = STTParserInterface.set_case
                value = STTCase.CAPITAL
            else:
                continue

            self._add_utterances_to_tree(utterances, callback, value, STTParseModes.SPELLING | STTParseModes.DICTATION)

    def _load_commands_list(self, item_list):
        if item_list == None:
            return

        for item in item_list:
            value=item.get("value")
            utterances=item.get("utterances")

            # In case there is only one
            if isinstance(utterances,str):
                utterances = [utterances]

            # Should we use getattr and setattr to make it leaner ?
            if value == "cancel":
                callback = STTParserInterface.cancel
                value = None
                modes = STTParseModes.SPELLING | STTParseModes.DICTATION
            elif value == "spelling":
                callback = STTParserInterface.set_mode
                value = STTParseModes.SPELLING
                modes = STTParseModes.ALL
            elif value == "dictation":
                callback = STTParserInterface.set_mode
                value = STTParseModes.DICTATION
                modes = STTParseModes.ALL
            elif value == "literal":
                callback = STTParserInterface.set_mode
                value = STTParseModes.LITERAL
                modes = STTParseModes.ALL
            elif value == "digits":
                callback = STTParserInterface.flip_use_digits
                value = None
                modes = STTParseModes.ALL
            else:
                continue

            self._add_utterances_to_tree(utterances, callback, value, modes)

    def _load_language(self, json_data):
        json_data = json_data.get("language")
        if json_data == None:
            LOG_MSG.debug("there is no language section")
            return

        # For all the following values, it has to be a complete override.
        # Using a cumulative approach ("+=") would not work as it does not
        # allow for removing characters previously set.
        # All the more so, as there is a default value for the following three
        # first values.
        self.no_space_after=json_data.get("no space after", self.no_space_after)
        self.no_space_before=json_data.get("no space before", self.no_space_before)
        self.capitalize_next=json_data.get("capitalize next", self.capitalize_next)
        self.digits=json_data.get("digits", self.digits)

    def _load_formatting_file(self):
        # Note: reset set formatting_file_valid to False
        self.reset()

        LOG_MSG.info("loading formatting file")
        json_data=self._current_locale.formatting
        if json_data is None:
            return

        self._load_language(json_data)

        # No section is compulsory
        self._load_commands_list(json_data.get("commands"))
        self._load_case_list(json_data.get("case"))
        self._load_diacritics_list(json_data.get("diacritics"))
        self._load_punctuation_list(json_data.get("punctuation"))
        self._load_replacements_list(json_data.get("custom"))
        self.formatting_file_valid=True

    def _load_overriding_file(self):
        if self.overriding_file_valid == True:
            # Note: following function will call reset and set
            # overriding_file_valid to False
            self._load_formatting_file()

        LOG_MSG.info("loading overriding file")
        json_data=self._current_locale.overriding
        if json_data is None:
            return

        # Note: this is pure override it is not cumulative or additive
        self._load_language(json_data)

        self._load_commands_list(json_data.get("commands"))
        self._load_case_list(json_data.get("case"))
        self._load_diacritics_list(json_data.get("diacritics"))
        self._load_punctuation_list(json_data.get("punctuation"))
        self._load_replacements_list(json_data.get("custom"))
        self.overriding_file_valid=True

    def _formatting_file_changed_cb(self, current_locale):
        self._load_formatting_file()
        self._load_overriding_file()
        self.emit("changed")

    def _overriding_file_changed_cb(self, current_locale, file_deleted):
        self._load_overriding_file()
        self.emit("changed")

    def reset(self):
        # This dictionary, digits, is used only in spelling mode
        self.digits={}

        # These values are used for automatic formatting.
        # We default to rules used for English but it can be overriden.
        self.no_space_before=" ….,)]}'-\t\n?!;:"
        self.no_space_after=" ([{@\n\t-"
        self.capitalize_next=".?!…"

        self._root=STTWordNode(0)

        self.formatting_file_valid=False
        self.overriding_file_valid=False
