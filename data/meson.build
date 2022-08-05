data_conf = configuration_data()
data_conf.set('libexecdir', libexecdir)
data_conf.set('datadir', datadir / meson.project_name())
data_conf.set('version', meson.project_version())
data_conf.set('python', python_prog.full_path())

# rf. i18n metainfo.xml
# http://www.freedesktop.org/software/appstream/docs/sect-Quickstart-Translation.html
# https://blogs.gnome.org/hughsie/2016/01/25/appdata-and-the-gettext-domain/
i18n.merge_file(
  input: configure_file(
    output: 'stt.appdata.xml.in',
    input: 'stt.appdata.xml.in.in',
    configuration: data_conf),
  output: 'stt.xml',
  po_dir: meson.project_source_root() / 'po',
  install: true,
  install_dir: ibusdir,
)

i18n.merge_file(
  input: configure_file(
    output: 'ibus-setup-stt.desktop.in',
    input: 'ibus-setup-stt.desktop.in.in',
    configuration: data_conf),
  output: 'ibus-setup-stt.desktop',
  type: 'desktop',
  po_dir: meson.project_source_root() / 'po',
  install: true,
  install_dir: get_option('datadir') / 'applications',
)

configure_file(
  input: 'ibus-engine-stt.in',
  output: 'ibus-engine-stt',
  configuration: data_conf,
  install: true,
  install_dir: get_option('libexecdir'),
  install_mode: 'rwxr-xr-x',
)

configure_file(
  input: 'ibus-setup-stt.in',
  output: 'ibus-setup-stt',
  configuration: data_conf,
  install: true,
  install_dir: get_option('libexecdir'),
  install_mode: 'rwxr-xr-x',
)

schema_file='org.freedesktop.ibus.engine.stt.gschema.xml'
configure_file(configuration: data_conf,
  output:schema_file,
  input:schema_file+'.in',
  install_dir: join_paths(datadir, 'glib-2.0/schemas'),
)

subdir('formatting')
subdir('numbers')
