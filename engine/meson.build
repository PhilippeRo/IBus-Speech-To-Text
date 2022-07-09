stt_sources = [
    'main.py',
    'mainconfig.py',
    'sttengine.py',
    'sttgstvosk.py',
    'sttgstfactory.py',
    'sttgstbase.py',
    'sttgsthandler.py',
    'sttsegmentprocess.py',
    'sttconfigdialog.py',
    'sttlocalerow.py',
    'sttvoskmodel.py',
    'sttcurrentlocale.py',
    'sttutterancetree.py',
    'sttshortcutrow.py',
    'sttshortcutdialog.py',
    'sttutterancerow.py',
    'sttmodelchooserdialog.py',
    'sttvoskmodelmanagers.py',
    'sttwordstodigits.py',
    'sttmodelrow.py'
    ]

gnome.compile_resources('ibus-engine-stt-config',
  'sttconfig.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: datadir / meson.project_name())


foreach source : stt_sources
  configure_file(
    input: source,
    output: source,
    copy: true
  )
endforeach

install_data(stt_sources)

utils_conf = configuration_data()
utils_conf.set('datadir', datadir / meson.project_name())
utils_conf.set('project_name', meson.project_name())
utils_conf.set('ibuscomponentpath', ibusdir)
utils_conf.set('appid', appid)
utils_conf.set('libexec', libexecdir)
utils_conf.set('version', meson.project_version())
utils_conf.set('license', meson.project_license())

configure_file(
  input: 'sttutils.py.in',
  output: 'sttutils.py',
  configuration: utils_conf,
  install: true,
  install_dir : datadir / meson.project_name()
)
