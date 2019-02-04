-- function tests
select packages_image('openwrt', '18.06.2', 'ar71xx/generic', 'v2'); 
-- bmon tmux vim

select transform('openwrt', '18.06.1', '18.06.2', 'tmux-light tmux-mega-addon');
-- tmux-full

select transform('openwrt', '18.06.1', '18.06.2', 'tmux-light');
-- tmux

-- select * from outdated_target();

select insert_packages_profile('openwrt', '18.06.2', 'ar71xx/generic', 'v2', 'Foobar v2', 'tmux vim bmon');
