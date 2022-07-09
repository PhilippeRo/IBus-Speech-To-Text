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

from gi.repository import GObject

from sttutils import *

from sttutterancetree import STTUtteranceTree, STTParserInterface, STTParseModes, STTCase
from sttwordstodigits import STTWordsToDigits

LOG_MSG=logging.getLogger()

class STTSegment():
    def __init__(self, segment=None):
        if segment != None:
            self._diacritic=segment._diacritic
            self._last_word=""
            self._utterance=""
        else:
            self._reset()

        self._previous = segment

    def _reset(self):
        self._diacritic=None
        self._last_word=""
        self._utterance = ""

    def is_empty(self):
        if self._diacritic == None and self._utterance == "":
            return True

        return False

class STTProcessContext():
    def __init__(self, context=None):
        if context == None:
            self._mode=STTParseModes.DICTATION
            self._case=STTCase.NONE
            self._w2n=STTWordsToDigits()
            self._first=None
            self._last=None
            return

        if context._first == None:
            # It means we are beginning a new segment
            self._first=context
        else:
            # We are analysing a new version of a segment
            self._first=context._first

        self._mode=self._first._mode
        self._case=self._first._case
        self._w2n=self._first._w2n

        self._last=context

    def changed(self):
        if self._mode != self._last._mode or self._w2n != self._last._w2n:
            return True

        return False

class STTSegmentProcess(GObject.GObject, STTParserInterface):
    __gtype_name__ = 'STTSegmentProcess'

    __gsignals__ = {
        "mode-changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self._parser = STTUtteranceTree()
        self._parser.connect("changed", self._parser_changed)

        self._context = STTProcessContext()
        self._update_caps()

        self._text_left=""
        self._init_text()

    def _update_caps(self):
        # Update our capacities
        if self._parser.formatting_file_valid == False:
            # Spelling is impossible
            self.can_spell=False
            if self._context._mode == STTParseModes.SPELLING:
                self._context._mode=STTParseModes.LITERAL

            if self._parser.overriding_file_valid == False:
                self.can_dictate=False
                if self._context._mode == STTParseModes.DICTATION:
                    self._context._mode=STTParseModes.LITERAL
            else:
                self.can_dictate=True
        else:
            self.can_spell=True
            self.can_dictate=True

    def _parser_changed(self, parser):
        LOG_MSG.debug("parsing capabilities changed")
        self._update_caps()
        self.emit("mode-changed")

    @property
    def pending_cancel_size(self):
        size = self._pending_cancel_size
        self._pending_cancel_size = 0
        return size

    @property
    def segment(self):
        if self._segment != None:
            return self._segment

        return self._last_segment

    @property
    def mode(self):
        return self._context._mode

    @mode.setter
    def mode(self, mode):
        self._context._mode = mode

    @property
    def can_use_digits(self):
        return self._context._w2n.can_use_digits

    @property
    def use_digits(self):
        return self._context._w2n.active

    @use_digits.setter
    def use_digits(self, use_digits):
        self._context._w2n.use_digits(use_digits)

    def _init_text(self):
        self._last_segment = STTSegment()
        self._segment = None
        self._pending_cancel_size = 0

    def reset(self):
        # Modes are not reset
        self._context._case=STTCase.NONE
        self._init_text()

    def is_processing(self):
        return bool(self._segment != None)

    # STTParserInterface method
    def cancel(self):
        # Reset case if lock not set
        if (self._context._case & STTCase.LOCK) == 0:
            self._context._case=STTCase.NONE

        if self._segment.is_empty() == True:
            # Remove previous segment from "parents", keep its size around.

            # _previous == None should not happen
            if self._segment._previous._previous != None:
                # When previous segment is None it means that we reached the
                # first bogus segment that contains the left text set by the
                # the engine.
                self._pending_cancel_size += len(self._segment._previous._utterance)
                self._segment._previous = self._segment._previous._previous
        else:
            # Note: that resets the diacritic
            self._segment._reset()

        # Update the context from the previous segment.
        # Reminder: diacritics are set to None
        self._text_left=self._segment._previous._last_word

        # TODO See if it would be possible to have two commands "cancel previous
        # word" / "cancel previous segment"

    # STTParserInterface method
    def set_case(self, case):
        self._context._case=case

    # STTParserInterface method
    def set_mode(self, mode):
        self._context._mode=mode

    # STTParserInterface method
    def flip_use_digits(self):
        self.use_digits = not self.use_digits

    # STTParserInterface method
    def add_diacritic(self, diacritic):
        # The [0] is the non combining unicode (ie U+005E for circumflex)
        # and [1] is the combining unicode character (ie U+0302 for circumflex)
        if self._segment._diacritic:
            self._segment._utterance += self._segment._diacritic[0]

        self._segment._diacritic = diacritic

    # STTParserInterface method
    def add_words(self, words):
        self._append_words(words)

    def _append_word(self, word):
        if self.mode == STTParseModes.SPELLING:
            word_num = self._parser.digits.get(word)
            if word_num != None:
                word = word_num
            elif len(word) > 0:
                # Allows to spell using the first letter of words (Alpha, ...)
                word = word[0]
        else :
            last_char=self._text_left[-1] if len(self._text_left) > 0 else ""

            if word not in self._parser.no_space_before and \
               last_char not in self._parser.no_space_after and \
               last_char != "":
                self._segment._utterance += " "

            if last_char.isspace() == True:
                last_char=self._text_left[-2] if len(self._text_left) > 1 else ""

            if (self._context._case & STTCase.LOWER) == 0 and \
               (last_char == "" or last_char in self._parser.capitalize_next):
                word = word.capitalize()

        if (self._context._case & STTCase.UPPER) != 0:
            word=word.upper()
        elif (self._context._case & STTCase.CAPITAL) != 0:
            word=word.capitalize()

        if self._segment._diacritic != None:
            self._segment._utterance += self._segment._diacritic[1]
            self._segment._diacritic = None

        self._segment._utterance += word

        if (self._context._case & STTCase.LOCK) == 0:
            self._context._case = STTCase.NONE

        # Note : we set _segment._last_word at the very end
        self._text_left = word

    def _append_words(self, words):
        if isinstance(words,str):
            self._append_word(words)
            return

        for word in words:
            self._append_word(word)

    def _utterance_process(self, utterance, text_left):
        self._context = STTProcessContext(self._context)
        self._segment = STTSegment(self._last_segment)

        # If we don't have text on the left use our last segment's last word
        # (which may be "").
        if text_left != "":
            LOG_MSG.info(" there is text on the left (%s)", text_left)
            self._text_left = text_left
        else:
            self._text_left = self._last_segment._last_word

        words = utterance.split()
        max_words = len(words)
        word_i = 0

        while word_i < max_words:
            new_word_i = self._parser.parse(self, words, word_i)
            if new_word_i != word_i:
                word_i = new_word_i
                continue

            new_word_i = self._context._w2n.parse(self, words, word_i)
            if new_word_i != word_i:
                word_i = new_word_i
                continue

            # Nothing found in tree and no number, no match, keep word
            self._append_word(words[word_i])
            word_i += 1

        self._segment._last_word=self._text_left

        if self._context.changed() == True:
            self.emit("mode-changed")

    def utterance_process_begin(self, utterance, text_left):
        self._utterance_process(utterance, text_left)

        if self._segment._diacritic != None:
            return self._segment._utterance + self._segment._diacritic[0]

        return self._segment._utterance

    def utterance_process_end(self, utterance, text_left):
        self._utterance_process(utterance, text_left)
        text = self._segment._utterance

        # If utterance is empty (no text, no diacritics), don't keep segment.
        if self._segment.is_empty() == False:
            self._last_segment=self._segment
        else:
            self._last_segment=self._segment._previous

        self._segment = None

        self._context._first = None
        self._context._last = None
        return text
