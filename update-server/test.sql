insert into releases select 'lede', '17.01.2' on conflict do nothing;
insert into subtargets (distro, release, target, subtarget) select 'lede', '17.01.2', 'x86', '64' on conflict do nothing;
insert into packages_default select 'lede', '17.01.2', 'x86', '64', 'tmux curl wget';
insert into packages_profile select 'lede', '17.01.2', 'x86', '64', 'Generic', 'usb hdmi';
insert into packages_hashes select 'pseudohash', 'tmux curl wget usb hdmi';
