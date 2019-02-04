-- insert tests
insert into distros (distro, distro_alias, latest) values ('openwrt', 'OpenWrt', '18.06.2');

insert into versions (distro, version, snapshots) 
values
    ('openwrt', '18.06.1', false),
    ('openwrt', '18.06.2', false);

insert into targets (distro, version, target) values ('openwrt', '18.06.2', 'ar71xx/generic');

insert into profiles
    (distro, version, target, profile, model) 
values
    ('openwrt', '18.06.2', 'ar71xx/generic', 'v2', 'Foobar v2');

insert into packages_available
    (distro, version, target, package_name, package_version) 
values
    ('openwrt', '18.06.2', 'ar71xx/generic', 'vim', '9.0');

insert into packages_default
    (distro, version, target, package_name) 
values
    ('openwrt', '18.06.2', 'ar71xx/generic', 'bmon'),
    ('openwrt', '18.06.2', 'ar71xx/generic', 'vim');

insert into manifest_packages
    (manifest_hash, package_name, package_version)
values
    ('abc', 'tmux', '1.0'),
    ('abc', 'bmon', '5.0'),
    ('abc', 'vim', '8.0');

insert into packages_hashes
    (packages_hash, package_name)
values
    ('qwe', 'tmux'),
    ('qwe', 'bmon');

insert into images
    (image_hash, distro, version, target, profile, manifest_hash, defaults_hash, worker, sysupgrade)
values
    ('zui', 'openwrt', '18.06.2', 'ar71xx/generic', 'v2', 'abc', '', 'worker0', 'firmware.bin');

insert into requests
    (request_hash, distro, version, target, profile, packages_hash, defaults_hash)
values
    ('asd', 'openwrt', '18.06.2', 'ar71xx/generic', 'v2', 'qwe', '');

insert into board_rename
    (distro, version, origname, newname)
values
    ('openwrt', '18.06.2', 'wrongname', 'goodname');

insert into transformations (distro, version, package, replacement)
values ('openwrt', '18.06.2', 'tmux-light', 'tmux');

insert into transformations (distro, version, package, replacement, context)
values ('openwrt', '18.06.2', 'tmux-light', 'tmux-full', 'tmux-mega-addon');

insert into transformations (distro, version, package)
values ('openwrt', '18.06.2', 'tmux-mega-addon');

