# IBus Speech To Text Input Method
A speech to text IBus Input Method using VOSK, written in Python. When enabled, you can dictate text to any application supporting IBus (most if not all applications do).

Description
============

This Input Method uses VOSK (https://github.com/alphacep/VOSK-api) for voice recognition and allows to dictate text in several languages in any application that supports IBus.
One of the main adavantages is that VOSK performs voice recognition locally and does not rely on an online service.

It works on Wayland and likely Xorg, though it has not been tested with the latter.

Since it uses IBus, it should work with most if not all applications since most modern toolkits (GTK, QT) all support IBus.

It has been tested with French and, to a lesser extent, with English but it should support all languages for which a voice recognition model is available on this page : https://alphacephei.com/VOSK/models

Note: you do not need to install the model manually, the setup tool can do it for you and lets you choose the model you want for your language (larger models tend to be more accurate of course but can require a lot of memory).

When there is a formatting file provided, IBus STT auto-formats the text that VOSK outputs (mainly adding spaces and capital letters when needed). Currently, such a file is only provided for French and American English but you can send me a new file for your language so I can integrate it (see the examples in data/formatting in the tree).

This file also adds support for voice commands to manage case, punctuation and diacritics.
For example, saying "capital letter california" yields "California" as a result and "comma" adds ",".

There is also a couple of possible voice commands, to switch between various modes (spelling, no formatting) or cancel dictated text.

All these commands can be configured and you can add new utterances to trigger a command.

You can add your own "voice shortcuts" for any language so that, for example, saying "write signature" yields:
"Best wishes,
John Doe"

See the setup tool.

Finally, if your language is supported, IBus STT can format numbers as digits. Only French and English were tested but it should work with more languages (see the examples in data/numbers in the tree).  

Dependencies
============

- meson > 0.59.0
- python 3.5.0
- babel (https://pypi.org/project/Babel/) which is probably packaged by your distribution
- ibus > 1.5.0 (the higher the better, it was tested with 1.5.26)
- Gio
- Gstreamer 1.20

The setup dialog depends on:
- libadwaita 1.1.0
- Gtk 4

You also need gst-VOSK installed (https://github.com/PhilippeRo/gst-VOSK/).

Building
============

To install it in /usr (where most distributions install IBus):
```
  meson setup builddir --prefix=/usr
  cd builddir
  meson compile
  meson install
```

Usage
============

Activate the Input Method through the IBus menu (that depends on your desktop) and start speaking.
It might seem obvious but the quality of the microphone used largely influences the accuracy of the voice recognition.

This Input Method can also be enabled and disabled with the default shorcut ("Win + Space") used to switch between IBus Input Methods. By default, when IBus STT is enabled, voice recognition is not started immediately but there is a setting to change this behaviour. If enabled, you can start and stop voice recognition with the above shortcut.
