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
import unicodedata

from gi.repository import GObject, IBus

from sttutils import *

from sttutterancetree import STTUtteranceTree, STTParserInterface, STTParseModes, STTCase
from sttwordstodigits import STTWordsToDigits

LOG_MSG=logging.getLogger()

class STTSegment():
    def __init__(self, segment=None):
        if segment is not None:
            self._diacritic=segment._diacritic
            self._last_word=""
            self._utterance=""
            self._shortcuts=[]
        else:
            self._reset()

        self._previous = segment

    def _reset(self):
        self._diacritic=None
        self._last_word=""
        self._utterance=""
        self._shortcuts=[]

    def is_empty(self):
        if self._diacritic == None and \
           self._utterance == "" and \
           self._shortcuts in [None,[]]:
            return True

        return False

class STTProcessContext():
    _w2n=STTWordsToDigits()

    def __init__(self, context=None):
        if context == None:
            self._mode=STTParseModes.DICTATION
            self._case=STTCase.NONE
            self._use_digits=False
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
        self._use_digits=self._first._use_digits

        self._last=context

    def changed(self):
        if self._mode != self._last._mode or self._use_digits != self._last._use_digits:
            return True

        return False

class STTSegmentProcess(GObject.GObject, STTParserInterface):
    __gtype_name__ = 'STTSegmentProcess'

    __gsignals__ = {
        "mode-changed": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "need-results" : (GObject.SIGNAL_RUN_FIRST, None, ()),
        "cancel": (GObject.SIGNAL_RUN_FIRST, None, (int,)),
        "shortcut": (GObject.SIGNAL_RUN_FIRST, None, (int, int,)),
        "partial-text": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        "final-text": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self._parser = STTUtteranceTree()
        self._parser.connect("changed", self._parser_changed)

        self._context = STTProcessContext()
        self._update_caps()

        self._supports_shortcuts=False

        self._text_left=""
        self._init_text()

    def _update_caps(self):
        # Update our capabilities
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

    # FIXME: this is unused
    @property
    def pending_cancel_size(self):
        size = self._pending_cancel_size
        self._pending_cancel_size = 0
        return size

    # FIXME: this is unused
    @property
    def segment(self):
        if self._segment != None:
            return self._segment

        return self._last_segment

    @property
    def supports_shorcuts(self):
        return self._supports_shortcuts

    @supports_shorcuts.setter
    def supports_shortcuts(self, supports_shortcuts):
        self._supports_shortcuts=supports_shortcuts

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
        return self._context._use_digits

    @use_digits.setter
    def use_digits(self, use_digits):
        self._context._use_digits=use_digits

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

        if self._segment.is_empty() is True:
            # The current segment is empty which means the cancelling word was
            # the first pronounced or that there was a succession of cancelling
            # words in the utterance.
            # Remove previous segment from "parents", keep its size around.

            # _previous == None should not happen
            if self._segment._previous._previous is not None:
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

    def add_shortcut(self, shortcut_str):
        if self._supports_shortcuts == False:
            return False

        (result,keyval,modifiers)=IBus.key_event_from_string(shortcut_str)
        if result == False:
            LOG_MSG.info("unsupported shortcut string (%s)", shortcut_str)
            return False

        # Get the size of current formatted utterance to remember where the
        # shortcut is.
        position=len(self._segment._utterance)
        self._segment._shortcuts.append((position, keyval, modifiers))
        return True

    def _append_word(self, word):
        if self.mode == STTParseModes.SPELLING:
            word_num = self._parser.digits.get(word)
            if word_num != None:
                word = word_num
            elif len(word) > 0:
                # Allows to spell using the first letter of words (Alpha, ...)
                word = word[0]
        else :
            last_char=self._text_left[-1] if self._text_left != "" else ""

            if word not in self._parser.no_space_before and \
               last_char not in self._parser.no_space_after and \
               last_char != "":
                self._segment._utterance += " "

            # Remove ALL white spaces
            last_char=last_char.rstrip()
            last_char=last_char if last_char == "" else last_char[-1]

            if (self._context._case & STTCase.LOWER) == 0 and \
               (last_char == "" or last_char in self._parser.capitalize_next):
                word = word.capitalize()

        if (self._context._case & STTCase.UPPER) != 0:
            word=word.upper()
        elif (self._context._case & STTCase.CAPITAL) != 0:
            word=word.capitalize()

        if self._segment._diacritic is not None:
            # Diacritics should be placed after the letter or some applications
            # like libreoffice will not combine the diacritic and the letter.
            letter=word[:1]

            # Check if the letter is not already combined. It might happen in
            # some cases that VOSK sends a combined character already; for
            # example "à" in French which makes the diacritic "`" redundant if
            # the user tried to add it.
            uncombined_letter=unicodedata.decomposition(letter).split()
            if uncombined_letter == [] or \
               chr(int(uncombined_letter[1], base=16)) != self._segment._diacritic[1]:
                letter=letter+self._segment._diacritic[1]

            word=letter+word[1:]
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
            self._text_left = text_left
        else:
            self._text_left = self._last_segment._last_word

        LOG_MSG.debug("left text (%s)", self._text_left)
        words = utterance.split()
        max_words = len(words)
        word_i = 0

        while word_i < max_words:
            new_word_i = self._parser.parse(self, words, word_i)
            if new_word_i != word_i:
                word_i = new_word_i
                continue

            if self._context._use_digits == True:
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

        if self._segment._diacritic is not None:
             self._segment._utterance =+ self._segment._diacritic[0]

        # If pending_cancel_size is not 0, then it means we need to delete text
        # on the left which is not possible while handling partial results.
        # We cannot perform any such deletion while we are in the middle of the
        # analysis of a partial utterance or it could be repeated the next time
        # we perform another analysis of the partial utterance.
        # So we need to do it as fast as possible and trigger a result to get on
        # Note: it does not matter that pending_cancel_size is reset to 0
        # after checking it since, it is not 0, it will be reset to proper value
        # since final_results() triggers the final analysis of the utterance.
        # Then, there is no need to send new partial text as the result would
        # not reflect the current state.
        if self._pending_cancel_size != 0 or self._segment._shortcuts not in [None,[]]:
            self._pending_cancel_size=0
            self.emit("need-results")
        else:
            self.emit("partial-text", self._segment._utterance)

    def utterance_process_end(self, utterance, text_left):
        self._utterance_process(utterance, text_left)
        text = self._segment._utterance

        if self._pending_cancel_size != 0:
            self.emit("cancel", self._pending_cancel_size)
            self._pending_cancel_size=0

        if self._segment._shortcuts not in [None,[]]:
            position=0
            for shortcut in self._segment._shortcuts:
                if shortcut[0] != position:
                    position=shortcut[0]
                    self.emit("final-text", text[:position])
                    text=text[position:]
                self.emit("shortcut", shortcut[1], shortcut[2])

        self.emit("final-text", text)

        # If utterance is empty (no text, no diacritics), don't keep segment.
        if self._segment.is_empty() is False:
            self._last_segment=self._segment
        else:
            self._last_segment=self._segment._previous

        self._segment = None

        self._context._first = None
        self._context._last = None
