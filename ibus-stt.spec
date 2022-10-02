Name:   ibus-stt
Version:  0.4.0
Release:  1%{?dist}
Summary:  A speech to text IBus Input Method using VOSK
BuildArch:  noarch
License:  GPLv3+
URL:    https://github.com/PhilippeRo/IBus-Speech-To-Text
Source0:  https://github.com/PhilippeRo/IBus-Speech-To-Text/archive/refs/tags/%{name}-%{version}.tar.gz

BuildRequires:  meson
BuildRequires:  python3-devel
BuildRequires:  ibus-devel >= 1.5.3
BuildRequires:  libadwaita-devel
BuildRequires:  gstreamer1-devel
BuildRequires:  desktop-file-utils
BuildRequires:  gettext

Requires:    ibus >= 1.5.3
Requires:    python3-dbus
Requires:    python3-babel
Requires:    gstreamer-1
Requires:    gobject-introspection
Requires:    gst-vosk >= 0.3.0
Requires:    glib2
Requires:    gtk4
Requires:    libadwaita
Requires:    dconf

%description
A speech to text IBus Input Method using VOSK, which can be used to dictate text to any application.

%prep
%autosetup

%build
%meson
%meson_build

%install
%meson_install

%py_byte_compile %{python3} %{buildroot}%{_datadir}/%{name}

%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%doc AUTHORS README.md
%{_libexecdir}/ibus-engine-stt
%{_libexecdir}/ibus-setup-stt
%{_datadir}/%{name}
%{_datadir}/ibus/component/stt.xml
%{_datadir}/applications/ibus-setup-stt.desktop
%{_datadir}/glib-2.0/schemas/org.freedesktop.ibus.engine.stt.gschema.xml

%changelog
* Sun Jul 31 2022 Philippe Rouquier <bonfire-app@wanadoo.fr> 0.2.0-1
- Initial version of the package
