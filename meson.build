project('ibus-stt',
          version: '0.2.0',
    meson_version: '>= 0.59.0',
          license: 'GPL-3.0-or-later',
  default_options: [ 'warning_level=2',
                   ],
)

i18n = import('i18n')

gnome = import('gnome')

python_prog = find_program('python3', version: '>=3.5')

prefix = get_option('prefix')
datadir = prefix / get_option('datadir')
localedir = prefix / get_option('localedir')
libexecdir = prefix / get_option('libexecdir')

appid='org.gnome.ibus-stt'

po_dir = meson.project_source_root() / 'po'

ibusdir = datadir / 'ibus' / 'component'
ibus_dep = dependency ('ibus-1.0',
                       version: '>= 1.5.0')

dependency('libadwaita-1', version: '>= 1.0')

# Post-install scripts
meson.add_install_script('build-aux/meson_post_install.py')

subdir('engine')
subdir('data')
subdir('po')
