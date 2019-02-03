 drop schema public cascade; create schema public;

create table if not exists sysupgrades_table (
    sysupgrade_id SERIAL PRIMARY KEY,
    sysupgrade varchar(100) unique
);

create table if not exists defaults_table (
    defaults_id serial primary key,
    defaults_hash varchar(64) unique,
    content text
);

create table if not exists worker_table (
    worker_id serial primary key,
    worker varchar(100),
    address varchar(100),
    public_key varchar(100),
    unique(worker)
);

create table if not exists distros_table (
    distro_id serial primary key,
    distro varchar(20) not null,
    distro_alias varchar(20) default '',
    distro_description text default '',
    latest varchar(20),
    unique(distro)
);

create or replace view distros as
select
    *
from distros_table;

create or replace rule insert_distros AS
ON insert TO distros DO INSTEAD (
    insert into distros_table (
        distro,
        distro_alias,
        distro_description,
        latest) 
    values (
        NEW.distro,
        NEW.distro_alias,
        NEW.distro_description, 
        NEW.latest)
    on conflict do nothing; 
);

create table if not exists versions_table(
    version_id serial primary key,
    distro_id integer not null,
    version varchar(20) not null,
    version_alias varchar(20) default '',
    version_description text default '',
    snapshots boolean default false,
    unique(distro_id, version),
    foreign key (distro_id) references distros_table(distro_id) ON DELETE CASCADE
);

create or replace view versions as
select
    version_id,
    distro,
    distro_alias,
    version,
    version_alias,
    version_description,
    snapshots
from distros join versions_table using (distro_id);

create or replace rule insert_versions AS
ON insert TO versions DO INSTEAD (
    insert into versions_table (
            distro_id,
            version,
            version_alias,
            version_description,
            snapshots)
        values (
            (select distro_id from distros where distro = NEW.distro),
            NEW.version,
            NEW.version_alias,
            NEW.version_description,
            NEW.snapshots
        ) on conflict do nothing;
);

create table if not exists targets_table(
    target_id serial primary key,
    version_id integer references versions_table(version_id),
    target varchar(50),
    supported boolean DEFAULT false,
    last_sync timestamp default date('1970-01-01'),
    unique(version_id, target)
);

create or replace view targets as
select
    * 
from versions 
join targets_table using (version_id);

create or replace rule insert_targets AS
ON insert TO targets DO INSTEAD (
    insert into targets_table (version_id, target) values (
        (select version_id from versions 
            where versions.distro = NEW.distro and version = NEW.version),
        NEW.target
    ) on conflict do nothing;
);

create or replace rule update_targets AS
ON update TO targets DO INSTEAD (
    update targets_table set
    supported = coalesce(NEW.supported, supported),
    last_sync = coalesce(NEW.last_sync, last_sync)
    where targets_table.target_id =
    (select target_id from targets where
        targets.distro = NEW.distro and
        targets.version = NEW.version and
        targets.target= NEW.target)
    returning
    old.*;
);

create or replace rule delete_targets as
on delete to targets do instead (
    delete from targets_table
    where old.target_id = targets_table.target_id;
);

create table if not exists profiles_table(
    profile_id serial primary key,
    target_id integer references targets_table(target_id) ON DELETE CASCADE,
    profile varchar(50),
    model varchar(100),
    unique(target_id, profile, model)
);

create or replace view profiles as
select
    *
from targets join profiles_table using (target_id);

create or replace rule insert_profiles AS
ON insert TO profiles DO INSTEAD (
    insert into profiles_table (target_id, profile, model) values (
        (select target_id from targets where
            targets.distro = NEW.distro and
            targets.version = NEW.version and
            targets.target = NEW.target),
        NEW.profile,
        NEW.model
    )  on conflict do nothing;
);

create or replace rule delete_profiles as
on delete to profiles do instead (
    delete from profiles_table
    where old.profile_id = profiles_table.profile_id;
);

create table if not exists packages_names(
    package_name_id serial primary key,
    package_name varchar(100) unique not null
);

create table if not exists packages_versions(
    package_version_id serial primary key,
    package_version varchar(100) unique not null
);

create table if not exists packages_available_table(
    target_id integer references targets_table(target_id) ON DELETE CASCADE,
    package_name_id integer references packages_names(package_name_id) ON DELETE CASCADE,
    package_version_id integer references packages_versions(package_version_id) ON DELETE CASCADE,
    primary key(target_id, package_name_id)
);

create or replace view packages_available as
select
    distro,
    version,
    target,
    package_name,
    package_version
from
    packages_available_table 
    join targets using (target_id)
    join packages_names using (package_name_id)
    join packages_versions using (package_version_id);

create or replace rule insert_available_packages AS
ON insert TO packages_available DO INSTEAD (
    insert into packages_names (package_name) values (NEW.package_name) on conflict do nothing;
    insert into packages_versions (package_version) values (NEW.package_version) on conflict do nothing;
    insert into packages_available_table values (
        (select target_id from targets where
            targets.distro = NEW.distro and
            targets.version = NEW.version and
            targets.target = NEW.target),
        (select package_name_id from packages_names where
            packages_names.package_name = NEW.package_name),
        (select package_version_id from packages_versions where
            packages_versions.package_version = NEW.package_version)
    ) on conflict (target_id, package_name_id) do update
    set package_version_id = (select package_version_id from packages_versions where
            packages_versions.package_version = NEW.package_version);
);

create table if not exists packages_default_table(
    target_id integer references targets_table(target_id) ON DELETE CASCADE,
    package_name_id integer references packages_names(package_name_id) ON DELETE CASCADE,
    primary key(target_id, package_name_id)
);

create or replace view packages_default as
select
	target_id,
	distro,
	version,
	target,
    package_name
from
	targets 
    join packages_default_table using (target_id)
    join packages_names using (package_name_id);

create or replace rule delete_packages_default as
on delete to packages_default do instead
delete from packages_default_table
where
	old.target_id = packages_default_table.target_id;

create or replace rule insert_packages_default AS
ON insert TO packages_default DO INSTEAD (
-- this shouldn't be required as the packages_available table is filled before     
        insert into packages_names (package_name) values (NEW.package_name) on conflict do nothing;
        insert into packages_default_table values (
            (select target_id from targets where
                targets.distro = NEW.distro and
                targets.version = NEW.version and
                targets.target = NEW.target),
            (select package_name_id from packages_names where
                packages_names.package_name = NEW.package_name)
        ) on conflict do nothing;
);

-- packages_profile

create table if not exists packages_profile_table(
    profile_id integer references profiles_table(profile_id) ON DELETE CASCADE,
    package_name_id integer references packages_names(package_name_id) ON DELETE CASCADE,
    primary key(profile_id, package_name_id)
);

create or replace view packages_profile as
select
    profile_id,
    distro,
    version,
    target,
    profile,
    model,
    package_name
from
    packages_profile_table
    join profiles using (profile_id)
    join packages_names using (package_name_id);

create or replace rule delete_packages_profile as
on delete to packages_profile do instead
    delete from packages_profile_table
    where old.profile_id = packages_profile_table.profile_id;

create or replace rule insert_packages_profile AS
ON insert TO packages_profile DO INSTEAD (
-- this shouldn't be required as the packages_available table is filled before     
    insert into packages_names (package_name) values (NEW.package_name) on conflict do nothing;
    insert into packages_profile_table values (
        (select profile_id from profiles where
            profiles.distro = NEW.distro and
            profiles.version = NEW.version and
            profiles.target = NEW.target and
            profiles.profile = NEW.profile),
        (select package_name_id from packages_names where packages_names.package_name = NEW.package_name)
    ) on conflict do nothing;
);

-- packages_image

create or replace function packages_image(
    distro varchar,
    version varchar,
    target varchar,
    profile varchar) 
    returns table(package_name varchar) as $$
begin
    return query select united.package_name from (
        select packages_profile.package_name from packages_profile
        where 
            packages_profile.distro = packages_image.distro and
            packages_profile.version = packages_image.version and
            packages_profile.target = packages_image.target and
            packages_profile.profile = packages_image.profile
        union
        select packages_default.package_name from packages_default
        where 
            packages_default.distro = packages_image.distro and
            packages_default.version = packages_image.version and
            packages_default.target = packages_image.target
        ) as united;
end
$$ LANGUAGE 'plpgsql';

-- manifest

create table if not exists manifests_table (
    manifest_id serial primary key,
    manifest_hash varchar(64) unique
);

create table if not exists manifest_packages_link (
    manifest_id integer references manifests_table(manifest_id) ON DELETE CASCADE,
    package_name_id integer references packages_names(package_name_id) ON DELETE CASCADE,
    package_version_id integer references packages_versions(package_version_id) ON DELETE CASCADE,
    unique(manifest_id, package_name_id, package_version_id)
);

create or replace view manifest_packages as
select
    manifest_id,
    manifest_hash,
    package_name,
    package_version
from
    manifests_table
    join manifest_packages_link using (manifest_id)
    join packages_names using (package_name_id)
    join packages_versions using (package_version_id);

create or replace rule insert_manifest_packages AS
ON insert TO manifest_packages DO INSTEAD (
    insert into manifests_table(manifest_hash) values (NEW.manifest_hash) on conflict do nothing;
    insert into packages_names (package_name) values (NEW.package_name) on conflict do nothing;
    insert into packages_versions (package_version) values (NEW.package_version) on conflict do nothing;
    insert into manifest_packages_link values (
        (select manifest_id from manifests_table
            where manifests_table.manifest_hash = NEW.manifest_hash),
        (select package_name_id from packages_names
            where packages_names.package_name = NEW.package_name),
        (select package_version_id from packages_versions
            where packages_versions.package_version = NEW.package_version)
    ) on conflict do nothing;
);

-- packages_hashes

create table if not exists packages_hashes_table (
    packages_hash_id serial primary key,
    packages_hash varchar(100) unique
);

create table if not exists packages_hashes_link(
    packages_hash_id integer references packages_hashes_table(packages_hash_id) ON DELETE CASCADE,
    package_name_id integer references packages_names(package_name_id) ON DELETE CASCADE,
    primary key(packages_hash_id, package_name_id)
);

create or replace view packages_hashes as
    select packages_hash, package_name
    from packages_hashes_link
    join packages_hashes_table using (packages_hash_id)
    join packages_names using (package_name_id);

create or replace rule insert_packages_hashes AS
ON insert TO packages_hashes DO INSTEAD (
    insert into packages_hashes_table (packages_hash) values (NEW.packages_hash) on conflict do nothing;
    insert into packages_names (package_name) values (NEW.package_name) on conflict do nothing;
    insert into packages_hashes_link values (
        (select packages_hashes_table.packages_hash_id from packages_hashes_table where
            packages_hashes_table.packages_hash = NEW.packages_hash),
        (select package_name_id from packages_names where packages_names.package_name = NEW.package_name)
    ) on conflict do nothing;
);

-- images
create table if not exists images_table (
    image_id SERIAL PRIMARY KEY,
    image_hash varchar(30) UNIQUE,
    profile_id integer references profiles_table(profile_id) ON DELETE CASCADE,
    manifest_id integer references manifests_table(manifest_id) ON DELETE CASCADE,
    worker_id integer references worker_table(worker_id) ON DELETE CASCADE,
    build_date timestamp default now(),
    sysupgrade_id integer references sysupgrades_table(sysupgrade_id) ON DELETE CASCADE,
    status varchar(20) DEFAULT 'untested',
    defaults_id integer references defaults_table(defaults_id) on delete cascade,
    vanilla boolean default false,
    build_seconds integer default 0
);

create or replace view images as
select
    image_id,
    image_hash,
    distro,
    distro_alias,
    version,
    version_alias,
    target,
    profile,
    model,
    manifest_hash,
    defaults_hash,
    worker,
    build_date,
    sysupgrade,
    status,
    vanilla,
    build_seconds,
    snapshots
from images_table
join profiles using (profile_id)
join manifests_table using (manifest_id)
join worker_table using (worker_id)
left join defaults_table using (defaults_id)
left join sysupgrades_table using (sysupgrade_id);

create or replace rule insert_images AS
ON insert TO images DO INSTEAD (
    insert into sysupgrades_table (sysupgrade) values (NEW.sysupgrade) on conflict do nothing;
    insert into worker_table(worker) values (NEW.worker) on conflict do nothing;
    insert into images_table (
        image_hash,
        profile_id,
        manifest_id,
        defaults_id,
        worker_id,
        sysupgrade_id,
        vanilla,
        build_seconds
    ) values (
        NEW.image_hash,
        (select profile_id from profiles where
            profiles.distro = NEW.distro and
            profiles.version = NEW.version and
            profiles.target = NEW.target and
            profiles.profile = NEW.profile),
        (select manifest_id from manifests_table where
            manifest_hash = NEW.manifest_hash),
        (select defaults_id from defaults_table where
            defaults_hash = NEW.defaults_hash),
        (select worker_id from worker_table where
            worker = NEW.worker),
        (select sysupgrade_id from sysupgrades_table where
            sysupgrade = NEW.sysupgrade),
        NEW.vanilla,
        NEW.build_seconds)
    on conflict do nothing;
);

create or replace rule update_images AS
ON update TO images DO INSTEAD
update images_table set
build_date = coalesce(NEW.build_date, build_date),
status = coalesce(NEW.status, status)
where images_table.image_hash = NEW.image_hash
returning
old.*;

create or replace rule delete_images as
on delete to images do instead
delete from images_table
where old.image_id = images_table.image_id;

-- tests

insert into distros (distro, distro_alias, latest) values ('openwrt', 'OpenWrt', '18.06.2');

insert into versions (distro, version, snapshots) values ('openwrt', '18.06.2', false);

insert into targets (distro, version, target) values ('openwrt', '18.06.2', 'ar71xx/generic');

insert into profiles
    (distro, version, target, profile, model) 
values
    ('openwrt', '18.06.2', 'ar71xx/generic', 'v2', 'Foobar v2');

insert into packages_available
    (distro, version, target, package_name, package_version) 
values
    ('openwrt', '18.06.2', 'ar71xx/generic', 'bmon', '1.0');

insert into packages_default
    (distro, version, target, package_name) 
values
    ('openwrt', '18.06.2', 'ar71xx/generic', 'bmon'),
    ('openwrt', '18.06.2', 'ar71xx/generic', 'vim');

insert into packages_profile
    (distro, version, target, profile, package_name) 
values
    ('openwrt', '18.06.2', 'ar71xx/generic', 'v2', 'tmux');

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
/*





create or replace view images_download as
select
id, image_hash,
    (CASE WHEN defaults_hash is null THEN
        ''
    ELSE
        'custom/' || defaults_hash || '/'
    end)
    || distro || '/'
    || version || '/'
    || target || '/'
    || target || '/'
    || profile || '/'
    || manifest_hash || '/'
    as file_path,
    sysupgrade
from images;

create table if not exists image_requests_table (
    id SERIAL PRIMARY KEY,
    request_hash varchar(30) UNIQUE,
    profile_id integer references profiles_table(id) ON DELETE CASCADE,
    packages_hash_id integer references packages_hashes_table(id) ON DELETE CASCADE,
    defaults_id integer references defaults_table(id) on delete cascade,
    image_id integer references images_table(id) ON DELETE CASCADE,
    status varchar(20) DEFAULT 'requested',
    request_date timestamp default now()
);

create or replace view image_requests as
select
    image_requests_table.id,
    request_hash,
    distro,
    version,
    target,
    target,
    profile,
    packages_hashes_table.hash as packages_hash,
    defaults_table.hash as defaults_hash,
    image_hash,
    image_requests_table.status,
    request_date,
    snapshots,
    image_requests_table.id - next_id + 1 as build_position
from
    profiles,
    packages_hashes_table,
    (select min(id) as next_id from image_requests_table where status = 'requested') as next,
    image_requests_table
left join defaults_table on defaults_table.id = image_requests_table.defaults_id
left join images_table on images_table.id = image_requests_table.image_id
where
    profiles.id = image_requests_table.profile_id and
    packages_hashes_table.id = image_requests_table.packages_hash_id;

create or replace rule insert_image_requests AS
ON insert TO image_requests DO INSTEAD
insert into image_requests_table (
    request_hash,
    profile_id,
    packages_hash_id,
    defaults_id
) values (
    NEW.request_hash,
    (select profiles.id from profiles where
        profiles.distro = NEW.distro and
        profiles.version = NEW.version and
        profiles.target = NEW.target and
        profiles.target = NEW.target and
        profiles.profile = NEW.profile),
    (select packages_hashes_table.id from packages_hashes_table where
        packages_hashes_table.hash = NEW.packages_hash),
    (select defaults_table.id from defaults_table where
        defaults_table.hash = NEW.defaults_hash)
    )
on conflict do nothing;

create or replace rule update_image_requests AS
ON update TO image_requests DO INSTEAD
update image_requests_table set
status = coalesce(NEW.status, status),
image_id = coalesce((select id from images_table where
        images_table.image_hash = NEW.image_hash), image_id)
where image_requests_table.request_hash = NEW.request_hash
returning
old.*;

create or replace rule delete_image_requests as
on delete to image_requests do instead
delete from image_requests_table
where old.id = image_requests_table.id;

create or replace view image_requests_targets as
select count(*) as requests, target_id
from image_requests_table, profiles_table
where profiles_table.id = image_requests_table.profile_id and status = 'requested'
group by (target_id)
order by requests desc;

CREATE TABLE IF NOT EXISTS board_rename_table (
    version_id INTEGER NOT NULL,
    origname varchar not null,
    newname varchar not null,
    FOREIGN KEY (version_id) REFERENCES versions_table(id),
    unique(version_id, origname)
);

create or replace view board_rename as
select distro, version, origname, newname
from board_rename_table
join versions on versions.id = board_rename_table.version_id;

create or replace function add_board_rename(distro varchar, version varchar, origname varchar, newname varchar) returns void as
$$
begin
    insert into board_rename_table (version_id, origname, newname) values (
        (select id from versions where
            versions.distro = add_board_rename.distro and
            versions.version = add_board_rename.version),
        add_board_rename.origname,
        add_board_rename.newname
    ) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_board_rename AS
ON insert TO board_rename DO INSTEAD
SELECT add_board_rename(
    NEW.distro,
    NEW.version,
    NEW.origname,
    NEW.newname
);

CREATE TABLE IF NOT EXISTS transformations_table (
    distro_id INTEGER NOT NULL, -- unused?
    version_id INTEGER NOT NULL,
    package_id INTEGER NOT NULL,
    replacement_id INTEGER,
    context_id INTEGER,
    FOREIGN KEY (distro_id) REFERENCES distros_table(id),
    FOREIGN KEY (version_id) REFERENCES versions_table(id),
    FOREIGN KEY (package_id) REFERENCES packages_names(id)
);

create or replace view transformations as
select distro, version, p.package_name as package, r.package_name as replacement, c.package_name as context
from transformations_table
join versions on versions.id = transformations_table.version_id
join packages_names p on transformations_table.package_id = p.id
left join packages_names r on transformations_table.replacement_id = r.id
left join packages_names c on transformations_table.context_id = c.id;

create or replace function add_transformations(distro varchar, version varchar, package varchar, replacement varchar, context varchar) returns void as
$$
begin
    -- evil hack to not insert Null names
    insert into packages_names (name) values (add_transformations.package), (coalesce(add_transformations.replacement, 'busybox')), (coalesce(add_transformations.context, 'busybox')) on conflict do nothing;
    insert into transformations_table (distro_id, version_id, package_id, replacement_id, context_id) values (
        (select id from distros where
            distros.name = add_transformations.distro),
        (select id from versions where
            versions.distro = add_transformations.distro and
            versions.version = add_transformations.version),
        (select id from packages_names where packages_name.package_name = add_transformations.package),
        (select id from packages_names where packages_name.package_name = add_transformations.replacement),
        (select id from packages_names where packages_name.package_name = add_transformations.context)
    ) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_transformations AS
ON insert TO transformations DO INSTEAD
SELECT add_transformations(
    NEW.distro,
    NEW.version,
    NEW.package,
    NEW.replacement,
    NEW.context
);

CREATE OR REPLACE FUNCTION transform_function(distro_id INTEGER, origversion_id INTEGER, targetversion_id INTEGER, origpkgar INTEGER[])
RETURNS INTEGER[] AS $$
WITH origpkgs AS (SELECT unnest(transform_function.origpkgar) AS pkgnameid)
SELECT ARRAY(
    SELECT DISTINCT COALESCE(transform_functionq.replacement_id, transform_functionq.pkgnameid) FROM (
        SELECT
        origpkgs.pkgnameid AS pkgnameid,
        transformations_table.package_id AS package_id,
        MAX(transformations_table.replacement_id) AS replacement_id
        FROM
        origpkgs
        LEFT OUTER JOIN
        (
            SELECT package_id, replacement_id, context_id FROM transformations_table WHERE
            transformations_table.distro_id = transform_function.distro_id AND
            transformations_table.version_id > transform_function.origversion_id AND
            transformations_table.version_id <= transform_function.targetversion_id
        ) AS transformations_table
        ON (origpkgs.pkgnameid = transformations_table.package_id)
        WHERE
        transformations_table.package_id IS NULL OR (
            origpkgs.pkgnameid = transformations_table.package_id AND (
                transformations_table.context_id IS NULL OR EXISTS (
                    SELECT origpkgs.pkgnameid FROM origpkgs WHERE origpkgs.pkgnameid = transformations_table.context_id
                )
                ) AND NOT (
                origpkgs.pkgnameid = transformations_table.package_id AND transformations_table.replacement_id IS NULL
            )
        )
        GROUP BY origpkgs.pkgnameid, transformations_table.package_id
    ) AS transform_functionq
)
$$ LANGUAGE sql;

create or replace function transform(distro varchar, origversion varchar, targetversion varchar, origpackages varchar) returns table(packages varchar) as $$
begin
    return query select package_name
        from unnest(transform_function(
            (select id from distros where
                distros.name = transform.distro),
            (select id from versions where
                versions.distro = transform.distro and
                versions.version = transform.origversion),
            (select id from versions where
                versions.distro = transform.distro and
                versions.version = transform.targetversion),
            (select array_agg(id) from packages_names, unnest(string_to_array(transform.origpackages, ' ')) as origpackages_rec where packages_names.package_name = origpackages_rec))) as result_ids
            join packages_names on packages_names.id = result_ids;
end
$$ LANGUAGE 'plpgsql';

-- TODO check if this function is much to expensive
create or replace view manifest_upgrades as
select
    distro,
    version,
    target,
    target,
    manifest_id,
    manifest_hash,
    json_object_agg(package_name,
    package_versions) as upgrades
    from (
            select
                    distro, version, target, target,
                    manifest_id, manifest_hash,
                    pa.package_name as package_name,
                    array[pa.package_version, mp.package_version] as package_versions
            from manifest_packages mp join packages_available pa using (package_name)
            where
                    pa.package_version != mp.package_version
    ) as upgrades group by (distro, version, target, target, manifest_id, manifest_hash);


create table if not exists upgrade_checks_table (
    id SERIAL PRIMARY KEY,
    check_hash varchar(30) UNIQUE,
    target_id integer references targets_table(id) ON DELETE CASCADE,
    manifest_id integer references manifests_table(id) ON DELETE CASCADE
);

create or replace view upgrade_checks as
select
uc.check_hash, s.distro, s.version, s.target, s.target, manifest_hash, mu.upgrades
from upgrade_checks_table uc, distros d, targets s, manifest_upgrades mu where
s.id = uc.target_id and
s.distro = d.name and
mu.manifest_id = uc.manifest_id and
mu.distro = s.distro and
mu.version = s.version and
mu.target = s.target and
mu.target = s.target;

create or replace rule insert_upgrade_checks AS
ON insert TO upgrade_checks DO INSTEAD
insert into upgrade_checks_table (check_hash, target_id, manifest_id) values (
    NEW.check_hash,
    (select targets.id from targets where
        targets.distro = NEW.distro and
        targets.version = NEW.version and
        targets.target = NEW.target and
        targets.target = NEW.target),
    (select manifests_table.id from manifests_table where
        manifests_table.hash = NEW.manifest_hash))
on conflict do nothing;
 drop schema public cascade; create schema public;

create table if not exists worker (
    worker_id serial primary key,
    name varchar(100),
    address varchar(100),
    public_key varchar(100),
    unique(name)
);

create table if not exists distros_table (
    distro_id serial primary key,
    distro varchar(20) not null,
    distro_alias varchar(20) default '',
    distro_description text default '',
    latest varchar(20),
    unique(distro_name)
);

create or replace view distros as
select
    *
from distros_table;

create or replace rule insert_distros AS
ON insert TO distros DO INSTEAD
    insert into distros_table (
        distro,
        distro_alias,
        distro_description,
        latest) 
    values (
        NEW.distro,
        NEW.distro_alias,
        NEW.distro_description, 
        NEW.latest)
    on conflict do nothing; 

create table if not exists versions_table(
    version_id serial primary key,
    distro_id integer not null,
    version_name varchar(20) not null,
    version_alias varchar(20) default '',
    version_description text default '',
    snapshots boolean default false,
    unique(distro_id, version_name),
    foreign key (distro_id) references distros_table(distro_id) ON DELETE CASCADE
);

create or replace view versions as
select
    version_id,
    distro,
    distro_alias,
    version_name,
    version_alias,
    version_description,
    snapshots
from distros join versions_table using (distro_id);

create or replace rule insert_versions AS
ON insert TO versions DO INSTEAD
    insert into versions_table (
            distro_id,
            version_name,
            version_alias,
            version_description,
            snapshots)
        values (
            (select distro_id from distros where distro = NEW.distro),
            NEW.version_name,
            NEW.version_alias,
            NEW.version_description,
            NEW.snapshots
        ) on conflict do nothing;

create table if not exists targets_table(
    target_id serial primary key,
    version_id integer references versions(version_id),
    target varchar(50),
    supported boolean DEFAULT false,
    last_sync timestamp default date('1970-01-01'),
    unique(version_id, target)
);

create or replace view targets as
select
    * 
from versions 
join targets_table using (version_id);
*/
