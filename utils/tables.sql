drop schema public cascade; create schema public;

create table if not exists worker (
    id serial primary key,
    name varchar(100),
    address varchar(100),
    public_key varchar(100),
    unique(name)
);

create table if not exists distributions (
    id serial primary key,
    name varchar(20) not null,
    alias varchar(20) default '',
    latest varchar(20),
    description text default '',
    unique(name)
);

create table if not exists versions_table(
    id serial primary key,
    distro_id integer not null,
    name varchar(20) not null,
    alias varchar(20) default '',
    description text default '',
    snapshots boolean default false,
    unique(distro_id, name),
    foreign key (distro_id) references distributions(id) ON DELETE CASCADE
);


create or replace view versions as
select
    versions_table.id,
    distributions.name as distro,
    versions_table.name as version,
    versions_table.alias,
    versions_table.description,
    snapshots
from distributions join versions_table on distributions.id = versions_table.distro_id;

create or replace function add_versions(distro varchar, version varchar, alias varchar, description text, snapshots boolean) returns void as
$$
begin
    insert into versions_table (distro_id, name, alias, description, snapshots) values (
        (select id from distributions where distributions.name = add_versions.distro),
        add_versions.version,
        add_versions.alias,
        add_versions.description,
        add_versions.snapshots
    ) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_versions AS
ON insert TO versions DO INSTEAD
SELECT add_versions(
    NEW.distro,
    NEW.version,
    NEW.alias,
    NEW.description,
    NEW.snapshots
);

create table if not exists subtargets_table(
    id serial primary key,
    version_id integer,
    target varchar(20),
    subtarget varchar(20),
    supported boolean DEFAULT false,
    last_sync timestamp default date('1970-01-01'),
    unique(version_id, target, subtarget)
);

create or replace view subtargets as
select
    subtargets_table.id,
    distro,
    version,
    snapshots,
    target,
    subtarget,
    supported,
    last_sync
from versions join subtargets_table on versions.id = subtargets_table.version_id;

create or replace function add_subtargets(distro varchar, version varchar, target varchar, subtarget varchar) returns void as
$$
begin
    insert into subtargets_table (version_id, target, subtarget) values (
        (select id from versions where versions.distro = add_subtargets.distro and versions.version = add_subtargets.version),
        add_subtargets.target,
        add_subtargets.subtarget
    ) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_subtargets AS
ON insert TO subtargets DO INSTEAD
SELECT add_subtargets(
    NEW.distro,
    NEW.version,
    NEW.target,
    NEW.subtarget
);

create or replace rule update_subtargets AS
ON update TO subtargets DO INSTEAD
update subtargets_table set
supported = coalesce(NEW.supported, supported),
last_sync = coalesce(NEW.last_sync, last_sync)
where subtargets_table.id =
(select id from subtargets where
    subtargets.distro = NEW.distro and
    subtargets.version = NEW.version and
    subtargets.target = NEW.target and
    subtargets.subtarget = NEW.subtarget)
returning
old.*;

create or replace rule delete_subtargets as
on delete to subtargets do instead
delete from subtargets_table
where old.id = subtargets_table.id;

create table if not exists profiles_table(
    id serial primary key,
    subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
    profile varchar(50),
    model varchar(100),
    unique(subtarget_id, profile, model)
);

create or replace view profiles as
select
    profiles_table.id,
    distro,
    version,
    target,
    subtarget,
    snapshots,
    profile,
    model
from subtargets, profiles_table
where profiles_table.subtarget_id = subtargets.id;

create or replace function add_profiles(distro varchar(20), version varchar(20), target varchar(20), subtarget varchar(20), name varchar(50), model varchar(100)) returns void as
$$
begin
    insert into profiles_table (subtarget_id, profile, model) values (
        (select id from subtargets where
            subtargets.distro = add_profiles.distro and
            subtargets.version = add_profiles.version and
            subtargets.target = add_profiles.target and
            subtargets.subtarget = add_profiles.subtarget),
        name,
        model
    )  on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_profiles AS
ON insert TO profiles DO INSTEAD
SELECT add_profiles(
    NEW.distro,
    NEW.version,
    NEW.target,
    NEW.subtarget,
    NEW.profile,
    NEW.model
);

create table if not exists packages_names(
    id serial primary key,
    package_name varchar(100) unique not null
);

create table if not exists packages_versions(
    id serial primary key,
    package_version varchar(100) unique not null
);

create table if not exists packages_available_table(
    subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
    package_id integer references packages_names(id) ON DELETE CASCADE,
    version_id integer references packages_versions(id) ON DELETE CASCADE,
    primary key(subtarget_id, package_id)
);

create or replace view packages_available as
select
    distro,
    version,
    target,
    subtarget,
    package_name,
    package_version
from
    packages_names,
    packages_versions,
    subtargets,
    packages_available_table
where
    subtargets.id = packages_available_table.subtarget_id and
    packages_available_table.package_id = packages_names.id and
    packages_available_table.version_id = packages_versions.id;

create or replace function add_packages_available(distro varchar(20), version varchar(20), target varchar(20), subtarget varchar(20), package_name varchar(100), package_version varchar(100)) returns void as
$$
begin
    insert into packages_names (package_name) values (add_packages_available.package_name) on conflict do nothing;
    insert into packages_versions (package_version) values (add_packages_available.package_version) on conflict do nothing;
    insert into packages_available_table values (
        (select id from subtargets where
            subtargets.distro = add_packages_available.distro and
            subtargets.version = add_packages_available.version and
            subtargets.target = add_packages_available.target and
            subtargets.subtarget = add_packages_available.subtarget),
        (select id from packages_names where
            packages_names.package_name = add_packages_available.package_name),
        (select id from packages_versions where
            packages_versions.package_version = add_packages_available.package_version)
    ) on conflict (subtarget_id, package_id) do update
    set version_id = (select id from packages_versions where
            packages_versions.package_version = add_packages_available.package_version);
end
$$ language 'plpgsql';

create or replace rule insert_available_default AS
ON insert TO packages_available DO INSTEAD
SELECT add_packages_available(
    NEW.distro,
    NEW.version,
    NEW.target,
    NEW.subtarget,
    NEW.package_name,
    NEW.package_version
);

create table if not exists packages_default_table(
    subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
    package integer references packages_names(id) ON DELETE CASCADE,
    primary key(subtarget_id, package)
);

create or replace view packages_default as
select distro, version, target, subtarget, string_agg(packages_names.package_name, ' ') as packages
from subtargets, packages_default_table, packages_names
where subtargets.id = packages_default_table.subtarget_id and packages_default_table.package = packages_names.id
group by (distro, version, target, subtarget);

create or replace function add_packages_default(distro varchar(20), version varchar(20), target varchar(20), subtarget varchar(20), packages text) returns void as
$$
declare
package varchar(100);
packages_array varchar(100)[] = string_to_array(packages, ' ');
begin
    FOREACH package IN array packages_array
    loop
        insert into packages_names (package_name) values (package) on conflict do nothing;
        insert into packages_default_table values (
            (select id from subtargets where
                subtargets.distro = add_packages_default.distro and
                subtargets.version = add_packages_default.version and
                subtargets.target = add_packages_default.target and
                subtargets.subtarget = add_packages_default.subtarget),
            (select id from packages_names where
                packages_names.package_name = package)
        ) on conflict do nothing;
    end loop;
end
$$ language 'plpgsql' ;

create or replace rule insert_packages_default AS
ON insert TO packages_default DO INSTEAD
SELECT add_packages_default(
    NEW.distro,
    NEW.version,
    NEW.target,
    NEW.subtarget,
    NEW.packages
);

create table if not exists packages_profile_table(
    profile_id integer references profiles_table(id) ON DELETE CASCADE,
    package integer references packages_names(id) ON DELETE CASCADE,
    primary key(profile_id, package)
);

create or replace view packages_profile as
select
distro,
    version,
    target,
    subtarget,
    profile,
    model,
    string_agg(packages_names.package_name, ' ') as packages
from
    packages_names,
    packages_profile_table,
    subtargets,
    profiles_table
where packages_profile_table.package = packages_names.id and packages_profile_table.profile_id = profiles_table.id and subtargets.id = profiles_table.subtarget_id
group by (distro, version, target, subtarget, profile, model) ;

create or replace function add_packages_profile(distro varchar(20), version varchar(20), target varchar(20), subtarget varchar(20), profile varchar(20), model varchar(50), packages text) returns void as
$$
declare
package varchar(100);
packages_array varchar(100)[] = string_to_array(packages, ' ');
begin
    insert into profiles (distro, version, target, subtarget, profile, model)
    values (distro, version, target, subtarget, profile, model);
    FOREACH package IN array packages_array
    loop
        insert into packages_names (package_name) values (package) on conflict do nothing;
        insert into packages_profile_table values (
            (select profiles.id from profiles where
                profiles.distro = add_packages_profile.distro and
                profiles.version = add_packages_profile.version and
                profiles.target = add_packages_profile.target and
                profiles.subtarget = add_packages_profile.subtarget and
                profiles.profile = add_packages_profile.profile),
            (select id from packages_names where packages_names.package_name = package)
        ) on conflict do nothing;
    end loop;
end
$$ language 'plpgsql' ;

create or replace rule insert_packages_profile AS
ON insert TO packages_profile DO INSTEAD
SELECT add_packages_profile(
    NEW.distro,
    NEW.version,
    NEW.target,
    NEW.subtarget,
    NEW.profile,
    NEW.model,
    NEW.packages
);

create table if not exists defaults_table (
    id serial primary key,
    hash varchar(64) unique,
    content text
);

create table if not exists manifest_table (
    id serial primary key,
    hash varchar(64) unique
);

create table if not exists manifest_packages_link (
    manifest_id integer references manifest_table(id) ON DELETE CASCADE,
    name_id integer references packages_names(id) ON DELETE CASCADE,
    version_id integer references packages_versions(id) ON DELETE CASCADE,
    unique(manifest_id, name_id, version_id)
);

create or replace view manifest_packages as
select manifest_table.id as manifest_id, manifest_table.hash as manifest_hash, package_name, package_version
from manifest_table, manifest_packages_link, packages_names, packages_versions
where
manifest_table.id = manifest_packages_link.manifest_id and
packages_names.id = manifest_packages_link.name_id and
packages_versions.id = manifest_packages_link.version_id;

create or replace function add_manifest_packages(manifest_hash varchar(64), package_name varchar(100), package_version varchar(100)) returns void as
$$
declare
begin
    insert into packages_names (package_name) values (add_manifest_packages.package_name) on conflict do nothing;
    insert into packages_versions (package_version) values (add_manifest_packages.package_version) on conflict do nothing;
    insert into manifest_packages_link values (
        (select id from manifest_table where manifest_table.hash = add_manifest_packages.manifest_hash),
        (select id from packages_names where packages_names.package_name = add_manifest_packages.package_name),
        (select id from packages_versions where packages_versions.package_version = add_manifest_packages.package_version)
    ) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_manifest_packages AS
ON insert TO manifest_packages DO INSTEAD
SELECT add_manifest_packages(
    NEW.manifest_hash,
    NEW.package_name,
    NEW.package_version
);

create table if not exists packages_hashes_table (
    id serial primary key,
    hash varchar(100) unique
);

create table if not exists packages_hashes_link(
    hash_id integer references packages_hashes_table(id) ON DELETE CASCADE,
    package_id integer references packages_names(id) ON DELETE CASCADE,
    primary key(hash_id, package_id)
);

create or replace view packages_hashes as
select pht.id, hash, coalesce(string_agg(pn.package_name, ' '), '') as packages
from packages_hashes_table pht
        left join packages_hashes_link phl on pht.id = phl.hash_id
        left join packages_names pn on phl.package_id = pn.id
group by (pht.id, hash);


create or replace function add_packages_hashes(hash varchar(20), packages text) returns void as
$$
declare
package varchar(100);
packages_array varchar(100)[] = string_to_array(packages, ' ');
begin
    insert into packages_hashes_table (hash) values (add_packages_hashes.hash) on conflict do nothing;
    FOREACH package IN array packages_array
    loop
        insert into packages_names (package_name) values (package) on conflict do nothing;
        insert into packages_hashes_link values (
            (select packages_hashes_table.id from packages_hashes_table where
                packages_hashes_table.hash = add_packages_hashes.hash),
            (select id from packages_names where packages_names.package_name = package)
        ) on conflict do nothing;
    end loop;
end
$$ language 'plpgsql';

create or replace rule insert_packages_hashes AS
ON insert TO packages_hashes DO INSTEAD
SELECT add_packages_hashes(
    NEW.hash,
    NEW.packages
);

create or replace view packages_image as
select distinct
packages_default.distro,
packages_default.version,
packages_default.target,
packages_default.subtarget,
profiles.profile,
packages_default.packages || ' ' || coalesce(packages_profile.packages, '') as packages
from profiles join packages_default on
packages_default.distro = profiles.distro and
packages_default.version = profiles.version and
packages_default.target = profiles.target and
packages_default.subtarget = profiles.subtarget
left join packages_profile on
packages_profile.distro = profiles.distro and
packages_profile.version = profiles.version and
packages_profile.target = profiles.target and
packages_profile.subtarget = profiles.subtarget and
packages_profile.profile = profiles.profile;

create table if not exists sysupgrade_files (
    id SERIAL PRIMARY KEY,
    sysupgrade varchar(100) unique
);

create table if not exists images_table (
    id SERIAL PRIMARY KEY,
    image_hash varchar(30) UNIQUE,
    profile_id integer references profiles_table(id) ON DELETE CASCADE,
    manifest_id integer references manifest_table(id) ON DELETE CASCADE,
    worker_id integer references worker(id) ON DELETE CASCADE,
    build_date timestamp,
    sysupgrade_id integer references sysupgrade_files(id) ON DELETE CASCADE,
    status varchar(20) DEFAULT 'untested',
    defaults_id integer references defaults_table(id) on delete cascade,
    vanilla boolean default false,
    build_seconds integer
);

create or replace view images as
select
    images_table.id,
    image_hash,
    distro,
    version,
    target,
    subtarget,
    profile,
    manifest_table.hash as manifest_hash,
    defaults_table.hash as defaults_hash,
    worker.name as worker,
    build_date,
    sysupgrade,
    status,
    vanilla,
    build_seconds,
    snapshots
from profiles,
    manifest_table,
    sysupgrade_files,
    worker,
    images_table
left join defaults_table on defaults_table.id = images_table.defaults_id
where
    profiles.id = images_table.profile_id and
    images_table.manifest_id = manifest_table.id and
    images_table.sysupgrade_id = sysupgrade_files.id and
    images_table.worker_id = worker.id
;

create or replace function add_image(
    image_hash varchar,
    distro varchar,
    version varchar,
    target varchar,
    subtarget varchar,
    profile varchar,
    manifest_hash varchar,
    defaults_hash varchar,
    worker varchar, 
    sysupgrade varchar,
    build_date timestamp,
    vanilla boolean,
    build_seconds decimal
)
returns void as
$$
begin
    insert into sysupgrade_files (sysupgrade) values (add_image.sysupgrade) on conflict do nothing;
    insert into worker(name) values (add_image.worker) on conflict do nothing;
    insert into images_table (image_hash, profile_id, manifest_id, defaults_id, worker_id, sysupgrade_id, build_date, vanilla, build_seconds) values (
        add_image.image_hash,
        (select profiles.id from profiles where
            profiles.distro = add_image.distro and
            profiles.version = add_image.version and
            profiles.target = add_image.target and
            profiles.subtarget = add_image.subtarget and
            profiles.profile = add_image.profile),
        (select manifest_table.id from manifest_table where
            manifest_table.hash = add_image.manifest_hash),
        (select defaults_table.id from defaults_table where
            defaults_table.hash = add_image.defaults_hash),
        (select worker.id from worker where
            worker.name = add_image.worker),
        (select sysupgrade_files.id from sysupgrade_files where
            sysupgrade_files.sysupgrade = add_image.sysupgrade),
        add_image.build_date,
        add_image.vanilla,
        add_image.build_seconds)
    on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_images AS
ON insert TO images DO INSTEAD
SELECT add_image(
    NEW.image_hash,
    NEW.distro,
    NEW.version,
    NEW.target,
    NEW.subtarget,
    NEW.profile,
    NEW.manifest_hash,
    NEW.defaults_hash,
    NEW.worker,
    NEW.sysupgrade,
    NEW.build_date,
    NEW.vanilla,
    NEW.build_seconds
);

create or replace rule update_images AS
ON update TO images DO INSTEAD
update images_table set
build_date = coalesce(new.build_date, build_date),
status = coalesce(NEW.status, status)
where images_table.image_hash = NEW.image_hash
returning
old.*;

create or replace rule delete_images as
on delete to images do instead
delete from images_table
where old.id = images_table.id;

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
    || subtarget || '/'
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
    status varchar(20) DEFAULT 'requested'
);

create or replace view image_requests as
select
    image_requests_table.id,
    request_hash,
    distro,
    version,
    target,
    subtarget,
    profile,
    packages_hashes_table.hash as packages_hash,
    defaults_table.hash as defaults_hash,
    image_hash,
    image_requests_table.status,
    image_requests_table.id - next_id as build_position
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
        profiles.subtarget = NEW.subtarget and
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

create or replace view image_requests_subtargets as
select count(*) as requests, subtarget_id
from image_requests_table, profiles_table
where profiles_table.id = image_requests_table.profile_id and status = 'requested'
group by (subtarget_id)
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
    FOREIGN KEY (distro_id) REFERENCES distributions(id),
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
        (select id from distributions where
            distributions.name = add_transformations.distro),
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
    return query select name
        from unnest(transform_function(
            (select id from distributions where
                distributions.name = transform.distro),
            (select id from versions where
                versions.distro = transform.distro and
                versions.version = transform.origversion),
            (select id from versions where
                versions.distro = transform.distro and
                versions.version = transform.targetversion),
            (select array_agg(id) from packages_names, unnest(string_to_array(transform.origpackages, ' ')) as origpackages_rec where packages_name.package_name = origpackages_rec))) as result_ids
            join packages_names on packages_names.id = result_ids;
end
$$ LANGUAGE 'plpgsql';

create or replace view images_info as
select distinct images.id, images.image_hash, distributions.alias, images.distro, images.version, profiles.model, profiles.profile, images.target, images.subtarget, manifest_hash, worker, build_date, build_seconds
            from images
        join profiles on
            images.distro = profiles.distro and
            images.version = profiles.version and
            images.target = profiles.target and
            images.subtarget = profiles.subtarget and
            images.profile = profiles.profile
        join distributions on
            distributions.name = profiles.distro
        order by id desc;

-- TODO check if this function is much to expensive
create or replace view manifest_upgrades as
select
    distro,
    version,
    target,
    subtarget,
    manifest_id,
    manifest_hash,
    json_object_agg(package_name,
    package_versions) as upgrades
    from (
            select
                    distro, version, target, subtarget,
                    manifest_id, manifest_hash,
                    pa.package_name as package_name,
                    array[pa.package_version, mp.package_version] as package_versions
            from manifest_packages mp join packages_available pa using (package_name)
            where
                    pa.package_version != mp.package_version
    ) as upgrades group by (distro, version, target, subtarget, manifest_id, manifest_hash);


create table if not exists upgrade_checks_table (
    id SERIAL PRIMARY KEY,
    check_hash varchar(30) UNIQUE,
    subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
    manifest_id integer references manifest_table(id) ON DELETE CASCADE
);

create or replace view upgrade_checks as
select
uc.check_hash, s.distro, s.version, s.target, s.subtarget, manifest_hash, mu.upgrades
from upgrade_checks_table uc, distributions d, subtargets s, manifest_upgrades mu where
s.id = uc.subtarget_id and
s.distro = d.name and
mu.manifest_id = uc.manifest_id and
mu.distro = s.distro and
mu.version = s.version and
mu.target = s.target and
mu.subtarget = s.subtarget;

create or replace rule insert_upgrade_checks AS
ON insert TO upgrade_checks DO INSTEAD
insert into upgrade_checks_table (check_hash, subtarget_id, manifest_id) values (
    NEW.check_hash,
    (select subtargets.id from subtargets where
        subtargets.distro = NEW.distro and
        subtargets.version = NEW.version and
        subtargets.target = NEW.target and
        subtargets.subtarget = NEW.subtarget),
    (select manifest_table.id from manifest_table where
        manifest_table.hash = NEW.manifest_hash))
on conflict do nothing;
