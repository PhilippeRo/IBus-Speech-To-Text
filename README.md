# IBus-Speech-To-Text
A speech to text IBus engine using VOSK written in Python.
One of the main adavantages is that VOSK does not rely on any online service and voice recognition is done on the local computer.

Description
============

This IBus engine uses VOSK (https://github.com/alphacep/vosk-api) for voice recognition and allows to dictate text in several languages in any application through IBus.
It supports Wayland and likely Xorg, though it has not been tested with the latter.

It has been tested with French and, to a lesser extent, with English but it should support all languages for which a voice recognition model is available on this page : https://alphacephei.com/vosk/models
Note: you do not need to install the model manually, the setup tool can do it for you and lets you choose the model you want for your language (larger models tend to be more accurate of course but can require a lot of memory).

When there is a formatting file provided, ibus-stt auto-formats the text that vosk outputs (mainly adding spaces and capital letters when needed). Currently only French and American English are supported but you can send me a new file for your language so I can integrate it (see the examples in data/formatting in the tree).
This file also adds support for managing case, punctuation and diacritics with voice (saying "capital letter california" yields "California" as a result). There are a couple of possible voice commands (switching between various modes, cancelling dictated text).

You can also add your own "shortcuts" for any language so that, for example, saying "write signature" yields:
"Best wishes,
John Doe"
See the setup tool.

If your language is supported, ibus-stt can format numbers as digits. Only French and English were tested but it should work with more languages (see the examples in data/numbers in the tree).  

Dependencies
============

- meson > 0.59.0
- python 3.5.0
- babel (https://pypi.org/project/Babel/) which is probably packaged by your distribution
- ibus > 1.5.0 (the higher the better, it was tested with 1.5.26)
- Gio
- libadwaita 1.1.0
- Gtk 4
- Gstreamer 1.20

You also need gst-vosk installed (https://github.com/PhilippeRo/gst-vosk/).

Building
============

To install it in /usr (where most distributions install IBus):
```
  meson setup builddir --prefix=/usr
  meson compile
  meson install
```

Usage
============

Activate the engine through the IBus menu (that depends on your desktop).

Note: voice recognition does not start immediately after the engine is enabled in the menu but there is a setting to do so if you want to.
