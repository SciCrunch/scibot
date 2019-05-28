# you must build this with --nodeps if you are not on a RHEL alike
%define     _unitdir       /lib/systemd/system
%define     _etcdir        /etc/systemd/system

# building on gentoo makes this /var/lib for some reason :/
%define     _localstatedir /var

%define     scibot_user  scibot
%define     scibot_group %{scibot_user}
%define     scibot_home  %{_localstatedir}/lib/scibot
%define     scibot_log   %{_localstatedir}/log/scibot

%define     name scibot
%define     version 9999
Name:       %{name}
Version:    %{version}
Release:    0
Summary:    curation workflow automation and coordination
License:    Apache-2.0
Url:        https://github.com/SciCrunch/scibot
BuildArch:  noarch
BuildRequires: systemd
BuildRequires: git
Requires:   bash
Requires:   python3
Requires(post):    systemd
Requires(preun):   systemd
Requires(postun):  systemd

Source1: scibot-bookmarklet.socket
Source2: scibot-bookmarklet.service
Source3: scibot-bookmarklet-sync.service
Source4: env.conf

%description
curation workflow automation and coordination

%prep

if [[ ! -d %{buildroot} ]]; then
	mkdir %{buildroot};
fi

%define gitroot scibot
if [[ ! -d %{gitroot} ]]; then
	git clone https://github.com/SciCrunch/scibot.git
fi

%build
#pushd %{gitroot}
#python3 setup.py bdist_wheel
#%py3_build
 
%install
install -p -D -m 644 %{SOURCE1} %{buildroot}/%{_unitdir}/scibot-bookmarklet.socket
install -p -D -m 644 %{SOURCE2} %{buildroot}/%{_unitdir}/scibot-bookmarklet.service
install -p -D -m 644 %{SOURCE3} %{buildroot}/%{_unitdir}/scibot-bookmarklet-sync.service
install -p -D -m 600 %{SOURCE4} %{buildroot}/%{_etcdir}/scibot-bookmarklet.service.d/env.conf
#%py3_install

%pre
getent group %{scibot_group} > /dev/null || groupadd -r %{scibot_group}
getent passwd %{scibot_user} > /dev/null || \
    useradd -r -m -d %{scibot_home} -g %{scibot_group} \
    -s /bin/bash -c "scibot services" %{scibot_user}
if [[ ! -d %{scibot_log} ]]; then
	mkdir %{scibot_log}  # owner?
	chown %{scibot_user}:%{scibot_group} %{scibot_log}
fi

%post
systemctl enable scibot-bookmarklet
systemctl enable scibot-bookmarklet-sync

%clean
rm -rf %{buildroot}

%files
%{_unitdir}/scibot-bookmarklet.socket
%{_unitdir}/scibot-bookmarklet.service
%{_unitdir}/scibot-bookmarklet-sync.service
%{_etcdir}/scibot-bookmarklet.service.d/env.conf

%changelog
# skip this for now
