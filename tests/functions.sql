-- function tests
select packages_image('openwrt', '18.06.2', 'ar71xx/generic', 'tl-wdr4300-v1'); 
-- bmon tmux vim

select transform('openwrt', '18.06.1', '18.06.2', 'tmux-light tmux-mega-addon');
-- tmux-full

select transform('openwrt', '18.06.1', '18.06.2', 'tmux-light');
-- tmux

-- select * from outdated_target();

select insert_packages_profile(
    'openwrt', '18.06.2', 'ar71xx/generic', 'tl-wdr4300-v1', 'TP-LINK TL-WDR4300 v1', 'tmux vim bmon');

-- select * from get_build_job();
