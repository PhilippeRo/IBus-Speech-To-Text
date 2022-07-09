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

from pathlib import Path

from babel import Locale

from sttcurrentlocale import stt_current_locale

from sttutils import stt_utils_get_system_data_path

# This class is very loosely based on w2ni18n module:
# https://github.com/bastie/w2ni18n
# It was largely remodelled and adapted to fit our needs and is not meant to be
# a general module

LOG_MSG=logging.getLogger()

class STTWordNode(dict):
    def __init__(self, depth=0):
        super().__init__()
        self.value=None
        self.depth=depth

class STTWordsToDigits():
    def __init__(self):
        self._current_locale=stt_current_locale()
        self._current_locale.connect("changed", self._current_locale_changed_cb)
        self._init_for_locale()

    def _reset(self):
        self._separator_symbol=None
        self._separator=None
        self._root=STTWordNode()

        self._measures={}
        self._ignore={}
        self._w2n={}
        self._n2w={}

        self.can_use_digits=False

    def _init_for_locale(self):
        self._reset()

        file_path=Path(stt_utils_get_system_data_path(), "numbers",
                       "config_"+self._current_locale.locale[:2]+".properties")

        LOG_MSG.debug("loading configuration file for locale (%s)",
                      self._current_locale.locale[:2])
        try:
            with file_path.open() as locale_file:
                for line in locale_file:
                    if line == "" or line.startswith("#") == True:
                        continue

                    (key, value)=line.split("=")
                    if key.startswith("replace:"):
                        key=key[len("replace:"):]
                        self._add_to_replace_tree(key, value.strip())
                    elif key.startswith("measure:"):
                        key=key[len("measure"):]
                        self._measures[int(value.strip())]=key
                    elif key.startswith("ignore:"):
                        key=key[len("ignore:"):]
                        self._ignore[key]=list(value.strip().split(","))
                    elif key.startswith("point"):
                        self._separator=value.strip()
                    else:
                        value=int(value)
                        self._w2n[key]=value
                        self._n2w[value]=key

        except:
            LOG_MSG.debug("could not load configuration file for locale (%s)",
                          self._current_locale.locale[:2])
            self._reset()
            return


        self._separator_symbol=Locale(self._current_locale.locale).number_symbols['decimal']
        self.can_use_digits=True

    def _current_locale_changed_cb(self, current_locale):
        LOG_MSG.debug("update number parsing module for new locale")
        self._init_for_locale()

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

    def _add_to_replace_tree(self, key, value):
        words=key.split()
        if words == None:
            return

        word_iter=iter(words)

        # Note: node is always created
        node=self._add_to_node(word_iter, self._root, 0)
        if node.value != None:
            LOG_MSG.debug("node already exists")
            return

        node.value=value

    def _find_node(self, words, word_i, node):
        word = words[word_i]
        node_next = node.get(word)
        if node_next == None:
            if node.value is not None:
                return node

            return None

        word_i += 1
        if word_i < len(words):
            # We haven't reached the end of the utterance
            return_node = self._find_node(words, word_i, node_next)
            if return_node != None:
                return return_node

        if node_next.value is not None:
            return node_next

        return None

    def parse(self, parser, words, word_i):
        max_word_num=len(words)

        # What follows is adapted from original function
        new_word_i=word_i
        new_word_radix=0
        new_word_ignore=0

        previous_word=""
        word=""

        decimal_prefix=""
        integer_part=-1
        temp_value=0
        result=0

        while new_word_i < max_word_num:
            previous_word=word
            node=self._find_node(words, new_word_i, self._root)
            word=node.value if node != None else words[new_word_i]

            if previous_word != "":
                # Ignore some words (for example "and" in "one hundred and one")
                words_before=self._ignore.get(word, None)
                if new_word_ignore == 0 and words_before != None:
                    # See that the previous number matches what should come before
                    if previous_word not in words_before:
                        break

                    LOG_MSG.debug("reached word to ignore")

                    # Make sure there is a number to parse afterwards
                    new_word_ignore=new_word_i
                    new_word_i += 1 if node is None else node.depth
                    continue

                # Deal with the decimal separator but only once
                if new_word_radix == 0 and word == self._separator:
                    LOG_MSG.debug("reached radix")

                    # Make sure there is a number to parse afterwards
                    new_word_radix=new_word_i
                    new_word_i += 1 if node is None else node.depth

                    integer_part=result+temp_value
                    temp_value=0
                    result = 0
                    continue

            # Find value
            word_value=self._w2n.get(word, None)
            if word_value == None:
                break

            # A few rules to know where to stop
            if word_value == 0:
                if integer_part == -1:
                    # for integer part, only accept 0 if it is the first number
                    if result == 0 and temp_value == 0:
                        new_word_i += 1 if node is None else node.depth

                    break

                if result != 0 or temp_value != 0:
                    break

                decimal_prefix += "0"
            elif word_value in range(1,10):
                # A unit cannot be preceded by a unit except 0 by itself
                if (temp_value % 10) != 0:
                    LOG_MSG.debug("number break 1")
                    break

                # For cases like "10 2" which is not 12
                temp_value_mod100=temp_value % 100
                if temp_value_mod100 != 0 and \
                   self._n2w.get(temp_value_mod100+word_value, None) is not None:
                    LOG_MSG.debug("number break 2")
                    break

                temp_value+=word_value
            elif word_value in range(10,100):
                if (temp_value % 100) != 0:
                    LOG_MSG.debug("number break 3")
                    break

                temp_value+=word_value
            elif word_value == 100:
                if temp_value not in range(0,10):
                    LOG_MSG.debug("number break 4")
                    break

                temp_value=100 if temp_value == 0 else temp_value*100
            elif word_value in self._measures:
                # Check that these words appear in the right sequence and only
                # once.
                if (result % (word_value*1000)) != 0:
                    LOG_MSG.debug("number break 5")
                    break

                if temp_value != 0:
                    result+=temp_value*word_value
                    temp_value=0
                else:
                    result+=word_value

            new_word_ignore=0
            new_word_i += 1 if node is None else node.depth

        if word_i == new_word_i:
            return word_i

        result+=temp_value
        if integer_part != -1:
            # if result == 0 then move back before the decimal point
            if result == 0:
                new_word_i=new_word_radix
                number_string=str(integer_part)
            else:
                number_string=str(integer_part) + \
                              self._separator_symbol + \
                              decimal_prefix + \
                              str(result)
                # Trim potential 0 at the end (if fractional part was 100 for example)
                number_string=number_string.rstrip("0")
        else:
            number_string=str(result)

        LOG_MSG.debug("final number string %s", number_string)
        parser.add_words(number_string)
        return new_word_i
