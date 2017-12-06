create table if not exists distributions (
	id serial primary key,
	name varchar(20) not null,
	alias varchar(20) default '',
	unique(name)
);

create table if not exists releases_table(
	id serial primary key,
	distro_id integer not null,
	name varchar(20) not null,
	alias varchar(20) default '',
	unique(distro_id, name),
	foreign key (distro_id) references distributions(id) ON DELETE CASCADE
);

create or replace view releases as
select releases_table.id, distributions.name as distro, releases_table.name as release, releases_table.alias
from distributions join releases_table on distributions.id = releases_table.distro_id;

create or replace function add_releases(distro varchar, release varchar, alias varchar) returns void as
$$
begin
	insert into distributions (name) values (add_releases.distro) on conflict do nothing;
	insert into releases_table (distro_id, name, alias) values (
		(select id from distributions where distributions.name = add_releases.distro),
		add_releases.release,
		add_releases.alias
	) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_releases AS
ON insert TO releases DO INSTEAD
SELECT add_releases(
	NEW.distro,
	NEW.release,
	NEW.alias
);

create table if not exists subtargets_table(
	id serial primary key,
	release_id integer,
	target varchar(20),
	subtarget varchar(20),
	supported boolean DEFAULT false,
	last_sync timestamp default date('1970-01-01'),
	unique(release_id, target, subtarget)
);

create or replace view subtargets as
select subtargets_table.id, distro, release, target, subtarget, supported, last_sync
from releases join subtargets_table on releases.id = subtargets_table.release_id;

create or replace function add_subtargets(distro varchar, release varchar, target varchar, subtarget varchar) returns void as
$$
begin
	insert into subtargets_table (release_id, target, subtarget) values (
		(select id from releases where releases.distro = add_subtargets.distro and releases.release = add_subtargets.release),
		add_subtargets.target,
		add_subtargets.subtarget
	) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_subtargets AS
ON insert TO subtargets DO INSTEAD
SELECT add_subtargets(
	NEW.distro,
	NEW.release,
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
	subtargets.release = NEW.release and
	subtargets.target = NEW.target and
	subtargets.subtarget = NEW.subtarget)
returning
old.*;

create table if not exists profiles_table(
	id serial primary key,
	subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
	profile varchar(50),
	model varchar(100),
	unique(subtarget_id, profile, model)
);

create or replace view profiles as
select profiles_table.id, distro, release, target, subtarget, profile, model
from subtargets, profiles_table
where profiles_table.subtarget_id = subtargets.id;

create or replace function add_profiles(distro varchar(20), release varchar(20), target varchar(20), subtarget varchar(20), name varchar(50), model varchar(100)) returns void as
$$
begin
	insert into profiles_table (subtarget_id, profile, model) values (
		(select id from subtargets where
			subtargets.distro = add_profiles.distro and
			subtargets.release = add_profiles.release and
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
	NEW.release,
	NEW.target,
	NEW.subtarget,
	NEW.profile,
	NEW.model
);

create table if not exists packages_names(
	id serial primary key,
	name varchar(100) unique not null
);

create table if not exists packages_versions(
	id serial primary key,
	version varchar(100) unique not null
);

create table if not exists packages_available_table(
	subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
	package_id integer references packages_names(id) ON DELETE CASCADE,
	version_id integer references packages_versions(id) ON DELETE CASCADE,
---	version varchar(100), -- gnunet 0.10.2-git-20170111-a4295da3df82817ff2fe1fa547374a96a2e0280b-1
	primary key(subtarget_id, package_id)

);

create or replace view packages_available as
select
distro, release, target, subtarget, name, version
from packages_names, packages_versions, subtargets, packages_available_table
where subtargets.id = packages_available_table.subtarget_id
	and packages_available_table.package_id = packages_names.id
	and packages_available_table.version_id = packages_versions.id;

create or replace function add_packages_available(distro varchar(20), release varchar(20), target varchar(20), subtarget varchar(20), name varchar(100), version varchar(100)) returns void as
$$
begin
	insert into packages_names (name) values (add_packages_available.name) on conflict do nothing;
	insert into packages_versions (version) values (add_packages_available.version) on conflict do nothing;
	insert into packages_available_table values (
		(select id from subtargets where
			subtargets.distro = add_packages_available.distro and
			subtargets.release = add_packages_available.release and
			subtargets.target = add_packages_available.target and
			subtargets.subtarget = add_packages_available.subtarget),
		(select id from packages_names where
			packages_names.name = add_packages_available.name),
		(select id from packages_versions where
			packages_versions.version = add_packages_available.version)
	) on conflict (subtarget_id, package_id) do update
	set version_id = (select id from packages_versions where
			packages_versions.version = add_packages_available.version);
end
$$ language 'plpgsql';

create or replace rule insert_available_default AS
ON insert TO packages_available DO INSTEAD
SELECT add_packages_available(
	NEW.distro,
	NEW.release,
	NEW.target,
	NEW.subtarget,
	NEW.name,
	NEW.version
);

create table if not exists packages_default_table(
	subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
	package integer references packages_names(id) ON DELETE CASCADE,
	primary key(subtarget_id, package)
);

create or replace view packages_default as
select distro, release, target, subtarget, string_agg(packages_names.name, ' ') as packages
from subtargets, packages_default_table, packages_names
where subtargets.id = packages_default_table.subtarget_id and packages_default_table.package = packages_names.id
group by (distro, release, target, subtarget);

create or replace function add_packages_default(distro varchar(20), release varchar(20), target varchar(20), subtarget varchar(20), packages text) returns void as
$$
declare
package varchar(40);
packages_array varchar(40)[] = string_to_array(packages, ' ');
begin
	FOREACH package IN array packages_array
	loop
		insert into packages_names (name) values (package) on conflict do nothing;
		insert into packages_default_table values (
			(select id from subtargets where
				subtargets.distro = add_packages_default.distro and
				subtargets.release = add_packages_default.release and
				subtargets.target = add_packages_default.target and
				subtargets.subtarget = add_packages_default.subtarget),
			(select id from packages_names where
				packages_names.name = package)
		) on conflict do nothing;
	end loop;
end
$$ language 'plpgsql' ;

create or replace rule insert_packages_default AS
ON insert TO packages_default DO INSTEAD
SELECT add_packages_default(
	NEW.distro,
	NEW.release,
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
distro, release, target, subtarget, profile, model,
string_agg(packages_names.name, ' ') as packages
from packages_names, packages_profile_table, subtargets, profiles_table
where packages_profile_table.package = packages_names.id and packages_profile_table.profile_id = profiles_table.id and subtargets.id = profiles_table.subtarget_id
group by (distro, release, target, subtarget, profile, model) ;

create or replace function add_packages_profile(distro varchar(20), release varchar(20), target varchar(20), subtarget varchar(20), profile varchar(20), model varchar(50), packages text) returns void as
$$
declare
package varchar(40);
packages_array varchar(40)[] = string_to_array(packages, ' ');
begin
	insert into profiles (distro, release, target, subtarget, profile, model)
	values (distro, release, target, subtarget, profile, model);
	FOREACH package IN array packages_array
	loop
		insert into packages_names (name) values (package) on conflict do nothing;
		insert into packages_profile_table values (
			(select profiles_table.id from profiles_table, subtargets where
				profiles_table.profile = add_packages_profile.profile and
				profiles_table.subtarget_id = subtargets.id and
				subtargets.distro = add_packages_profile.distro and
				subtargets.release = add_packages_profile.release and
				subtargets.target = add_packages_profile.target and
				subtargets.subtarget = add_packages_profile.subtarget),
			(select id from packages_names where packages_names.name = package)
		) on conflict do nothing;
	end loop;
end
$$ language 'plpgsql' ;

create or replace rule insert_packages_profile AS
ON insert TO packages_profile DO INSTEAD
SELECT add_packages_profile(
	NEW.distro,
	NEW.release,
	NEW.target,
	NEW.subtarget,
	NEW.profile,
	NEW.model,
	NEW.packages
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
select manifest_table.id, as manifest_id, manifest_table.hash as manifest_hash, name, version
from manifest_table, manifest_packages_link, packages_names, packages_versions
where
manifest_table.id = manifest_packages_link.manifest_id and
packages_names.id = manifest_packages_link.name_id and
packages_versions.id = manifest_packages_link.version_id;

create or replace function add_manifest_packages(manifest_hash varchar(64), name varchar(100), version varchar(100)) returns void as
$$
declare
begin
	insert into packages_names (name) values (add_manifest_packages.name) on conflict do nothing;
	insert into packages_versions (version) values (add_manifest_packages.version) on conflict do nothing;
	insert into manifest_packages_link values (
		(select id from manifest_table where manifest_table.hash = add_manifest_packages.manifest_hash),
		(select id from packages_names where packages_names.name = add_manifest_packages.name),
		(select id from packages_versions where packages_versions.version = add_manifest_packages.version)
	) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_manifest_packages AS
ON insert TO manifest_packages DO INSTEAD
SELECT add_manifest_packages(
	NEW.manifest_hash,
	NEW.name,
	NEW.version
);

create table if not exists packages_hashes_table (
	id serial primary key,
	hash varchar(40) unique
);

create table if not exists packages_hashes_link(
	hash_id integer references packages_hashes_table(id) ON DELETE CASCADE,
	package_id integer references packages_names(id) ON DELETE CASCADE,
	primary key(hash_id, package_id)
);

create or replace view packages_hashes as
select packages_hashes_table.id, hash, string_agg(packages_names.name, ' ') as packages
from packages_names, packages_hashes_table, packages_hashes_link
where
packages_hashes_table.id = packages_hashes_link.hash_id and
packages_names.id = packages_hashes_link.package_id
group by (packages_hashes_table.id, hash);

create or replace function add_packages_hashes(hash varchar(20), packages text) returns void as
$$
declare
package varchar(40);
packages_array varchar(40)[] = string_to_array(packages, ' ');
begin
	insert into packages_hashes_table (hash) values (add_packages_hashes.hash) on conflict do nothing;
	FOREACH package IN array packages_array
	loop
		insert into packages_names (name) values (package) on conflict do nothing;
		insert into packages_hashes_link values (
			(select packages_hashes_table.id from packages_hashes_table where
				packages_hashes_table.hash = add_packages_hashes.hash),
			(select id from packages_names where packages_names.name = package)
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
packages_default.release,
packages_default.target,
packages_default.subtarget,
profiles.profile,
packages_default.packages || ' ' || coalesce(packages_profile.packages, '') as packages
from profiles join packages_default on
packages_default.distro = profiles.distro and
packages_default.release = profiles.release and
packages_default.target = profiles.target and
packages_default.subtarget = profiles.subtarget
left join packages_profile on
packages_profile.distro = profiles.distro and
packages_profile.release = profiles.release and
packages_profile.target = profiles.target and
packages_profile.subtarget = profiles.subtarget and
packages_profile.profile = profiles.profile;

create table if not exists imagebuilder_requests (
	distro text,
	release text,
	target text,
	subtarget text
);

create table if not exists imagebuilder_table (
	id SERIAL PRIMARY KEY,
	subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
	status varchar(20) DEFAULT 'requested' -- 'ready', 'disabled', 'failded'
);

create or replace view imagebuilder as
select
imagebuilder_table.id, distro, release, target, subtarget, status
from subtargets, imagebuilder_table
where
subtargets.id = imagebuilder_table.subtarget_id;

create or replace rule insert_imagebuilder AS
ON insert TO imagebuilder DO INSTEAD
insert into imagebuilder_table (subtarget_id)  values (
	(select id from subtargets where
		subtargets.distro = NEW.distro and
		subtargets.release = NEW.release and
		subtargets.target = NEW.target and
		subtargets.subtarget = NEW.subtarget)
) on conflict do nothing;

create or replace rule update_imagebuilder AS
ON update TO imagebuilder DO INSTEAD
update imagebuilder_table set
status = coalesce(NEW.status, status)
where imagebuilder_table.subtarget_id =
(select id from subtargets where
	subtargets.distro = NEW.distro and
	subtargets.release = NEW.release and
	subtargets.target = NEW.target and
	subtargets.subtarget = NEW.subtarget)
returning
old.*;

create table if not exists sysupgrade_suffixes (
	id SERIAL PRIMARY KEY,
	sysupgrade_suffix varchar(30) unique
);

create table if not exists images_table (
	id SERIAL PRIMARY KEY,
	image_hash varchar(30) UNIQUE,
	profile_id integer references profiles_table(id) ON DELETE CASCADE,
	manifest_id integer references manifest_table(id) ON DELETE CASCADE,
	network_profile varchar(30),
	checksum varchar(32),
	filesize integer,
	build_date timestamp,
	sysupgrade_suffix_id integer references sysupgrade_suffixes(id) ON DELETE CASCADE,
	status varchar(20) DEFAULT 'untested',
	subtarget_in_name boolean,
	profile_in_name boolean,
	vanilla boolean,
	build_seconds integer
);

create or replace view images as
select
images_table.id, image_hash, distro, release, target, subtarget, profile, hash as manifest_hash, network_profile, checksum, filesize, build_date, sysupgrade_suffix, status, subtarget_in_name, profile_in_name, vanilla, build_seconds
from profiles, images_table, manifest_table, sysupgrade_suffixes
where
profiles.id = images_table.profile_id and
images_table.manifest_id = manifest_table.id and
images_table.sysupgrade_suffix_id = sysupgrade_suffixes.id;

create or replace function add_image(image_hash varchar, distro varchar, release varchar, target varchar, subtarget varchar, profile varchar, manifest_hash varchar, network_profile varchar, checksum varchar, filesize integer, sysupgrade_suffix varchar, build_date timestamp, subtarget_in_name boolean, profile_in_name boolean, vanilla boolean, build_seconds decimal) returns void as
$$
begin
	insert into sysupgrade_suffixes (sysupgrade_suffix) values (add_image.sysupgrade_suffix) on conflict do nothing;
	insert into images_table (image_hash, profile_id, manifest_id, network_profile, checksum, filesize, sysupgrade_suffix_id, build_date, subtarget_in_name, profile_in_name, vanilla, build_seconds) values (
		add_image.image_hash,
		(select profiles.id from profiles where
			profiles.distro = add_image.distro and
			profiles.release = add_image.release and
			profiles.target = add_image.target and
			profiles.subtarget = add_image.subtarget and
			profiles.profile = add_image.profile),
		(select manifest_table.id from manifest_table where
			manifest_table.hash = add_image.manifest_hash),
		add_image.network_profile,
		add_image.checksum,
		add_image.filesize,
		(select sysupgrade_suffixes.id from sysupgrade_suffixes where
			sysupgrade_suffixes.sysupgrade_suffix = add_image.sysupgrade_suffix),
		add_image.build_date,
		add_image.subtarget_in_name,
		add_image.profile_in_name,
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
	NEW.release,
	NEW.target,
	NEW.subtarget,
	NEW.profile,
	NEW.manifest_hash,
	NEW.network_profile,
	NEW.checksum,
	NEW.filesize,
	NEW.sysupgrade_suffix,
	NEW.build_date,
	NEW.subtarget_in_name,
	NEW.profile_in_name,
	NEW.vanilla,
	NEW.build_seconds
);

create or replace rule update_images AS
ON update TO images DO INSTEAD
update images_table set
checksum = coalesce(new.checksum, checksum),
filesize = coalesce(new.filesize, filesize),
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
	distro || '/'
	|| release || '/'
	|| target || '/'
	|| subtarget || '/'
	|| profile || '/'
	|| (CASE vanilla WHEN true THEN 'vanilla/' ELSE  manifest_hash || '/'  END)
	|| (CASE network_profile WHEN '' THEN '' ELSE  network_profile || '/'  END)
	as file_path,
    distro || '-'
	|| (CASE release WHEN 'snapshot' THEN '' ELSE release || '-'  END)
	|| (CASE vanilla WHEN true THEN '' ELSE  manifest_hash || '-'  END)
	|| (CASE network_profile WHEN '' THEN '' ELSE replace(replace(network_profile, '/', '-'), '.', '-') || '-' END)
	|| target || '-'
	|| (CASE subtarget_in_name WHEN false THEN '' ELSE  subtarget || '-'  END)
	|| (CASE profile_in_name WHEN false THEN '' ELSE profile || '-'  END)
	|| sysupgrade_suffix
	as file_name,
	checksum, filesize
from images;

create table if not exists image_requests_table (
	id SERIAL PRIMARY KEY,
	request_hash varchar(30) UNIQUE,
	profile_id integer references profiles_table(id) ON DELETE CASCADE,
	packages_hash_id integer references packages_hashes_table(id) ON DELETE CASCADE,
	network_profile varchar(30),
	image_id integer references images_table(id) ON DELETE CASCADE,
	status varchar(20) DEFAULT 'requested'
);

create or replace view image_requests as
select
image_requests_table.id, request_hash, distro, release, target, subtarget, profile, hash as packages_hash, image_requests_table.network_profile, image_hash, image_requests_table.status
from profiles, packages_hashes_table, image_requests_table left join images_table on
images_table.id = image_requests_table.image_id
where
profiles.id = image_requests_table.profile_id and
packages_hashes_table.id = image_requests_table.packages_hash_id;

create or replace rule insert_image_requests AS
ON insert TO image_requests DO INSTEAD
insert into image_requests_table (request_hash, profile_id, packages_hash_id, network_profile) values (
	NEW.request_hash,
	(select profiles.id from profiles where
		profiles.distro = NEW.distro and
		profiles.release = NEW.release and
		profiles.target = NEW.target and
		profiles.subtarget = NEW.subtarget and
		profiles.profile = NEW.profile),
	(select packages_hashes_table.id from packages_hashes_table where
		packages_hashes_table.hash = NEW.packages_hash),
	NEW.network_profile)
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

create or replace view image_requests_subtargets as
select count(*) as requests, subtarget_id
from image_requests_table, profiles_table
where profiles_table.id = image_requests_table.profile_id and status = 'requested'
group by (subtarget_id)
order by requests desc;

create table if not exists worker (
	id serial primary key,
	name varchar(100),
	address varchar(100),
	public_key varchar(100),
	heartbeat timestamp
);

create table if not exists worker_skills (
	worker_id integer references worker(id) ON DELETE CASCADE,
	subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
	status varchar(20) DEFAULT 'init'
);

create or replace view worker_imagebuilder as
select distinct distro, release, target, subtarget
from worker_skills join subtargets
on worker_skills.subtarget_id = subtargets.id;

create or replace view worker_skills_subtargets as
select count(*) as worker, subtarget_id
from worker_skills
where status = 'ready'
group by (subtarget_id)
order by worker desc;

create or replace view worker_needed as
select image_requests_subtargets.subtarget_id, coalesce(worker, 0) as worker, requests
from image_requests_subtargets left outer join worker_skills_subtargets
on worker_skills_subtargets.subtarget_id = image_requests_subtargets.subtarget_id
order by worker, requests desc
limit 1;


CREATE TABLE IF NOT EXISTS board_rename_table (
	release_id INTEGER NOT NULL,
	origname varchar not null,
	newname varchar not null,
	FOREIGN KEY (release_id) REFERENCES releases_table(id),
	unique(release_id, origname)
);

create or replace view board_rename as
select distro, release, origname, newname
from board_rename_table
join releases on releases.id = board_rename_table.release_id;

create or replace function add_board_rename(distro varchar, release varchar, origname varchar, newname varchar) returns void as
$$
begin
	insert into board_rename_table (release_id, origname, newname) values (
		(select id from releases where
			releases.distro = add_board_rename.distro and
			releases.release = add_board_rename.release),
		add_board_rename.origname,
		add_board_rename.newname
	) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_board_rename AS
ON insert TO board_rename DO INSTEAD
SELECT add_board_rename(
	NEW.distro,
	NEW.release,
	NEW.origname,
	NEW.newname
);

CREATE TABLE IF NOT EXISTS transformations_table (
	distro_id INTEGER NOT NULL, -- unused?
	release_id INTEGER NOT NULL,
	package_id INTEGER NOT NULL,
	replacement_id INTEGER,
	context_id INTEGER,
	FOREIGN KEY (distro_id) REFERENCES distributions(id),
	FOREIGN KEY (release_id) REFERENCES releases_table(id),
	FOREIGN KEY (package_id) REFERENCES packages_names(id)
);

create or replace view transformations as
select distro, release, p.name as package, r.name as replacement, c.name as context
from transformations_table
join releases on releases.id = transformations_table.release_id
join packages_names p on transformations_table.package_id = p.id
left join packages_names r on transformations_table.replacement_id = r.id
left join packages_names c on transformations_table.context_id = c.id;

create or replace function add_transformations(distro varchar, release varchar, package varchar, replacement varchar, context varchar) returns void as
$$
begin
	-- evil hack to not insert Null names
	insert into packages_names (name) values (add_transformations.package), (coalesce(add_transformations.replacement, 'busybox')), (coalesce(add_transformations.context, 'busybox')) on conflict do nothing;
	insert into transformations_table (distro_id, release_id, package_id, replacement_id, context_id) values (
		(select id from distributions where
			distributions.name = add_transformations.distro),
		(select id from releases where
			releases.distro = add_transformations.distro and
			releases.release = add_transformations.release),
		(select id from packages_names where packages_names.name = add_transformations.package),
		(select id from packages_names where packages_names.name = add_transformations.replacement),
		(select id from packages_names where packages_names.name = add_transformations.context)
	) on conflict do nothing;
end
$$ language 'plpgsql';

create or replace rule insert_transformations AS
ON insert TO transformations DO INSTEAD
SELECT add_transformations(
	NEW.distro,
	NEW.release,
	NEW.package,
	NEW.replacement,
	NEW.context
);

CREATE OR REPLACE FUNCTION transform_function(distro_id INTEGER, origrelease_id INTEGER, targetrelease_id INTEGER, origpkgar INTEGER[])
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
			transformations_table.release_id > transform_function.origrelease_id AND
			transformations_table.release_id <= transform_function.targetrelease_id
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

create or replace function transform(distro varchar, origrelease varchar, targetrelease varchar, origpackages varchar) returns table(packages varchar) as $$
begin
	return query select name
		from unnest(transform_function(
			(select id from distributions where
				distributions.name = transform.distro),
			(select id from releases where
				releases.distro = transform.distro and
				releases.release = transform.origrelease),
			(select id from releases where
				releases.distro = transform.distro and
				releases.release = transform.targetrelease),
			(select array_agg(id) from packages_names, unnest(string_to_array(transform.origpackages, ' ')) as origpackages_rec where packages_names.name = origpackages_rec))) as result_ids
			join packages_names on packages_names.id = result_ids;
end
$$ LANGUAGE 'plpgsql';

create or replace view images_info as
select distinct images.id, images.image_hash, distributions.alias, images.distro, images.release, profiles.model, images.target, images.subtarget, manifest_hash, network_profile, build_date, images.checksum, file_path, file_name,  images.filesize
            from images
				join images_download on
					images.image_hash = images_download.image_hash
				join profiles on
					images.distro = profiles.distro and
					images.release = profiles.release and
					images.target = profiles.target and
					images.subtarget = profiles.subtarget and
					images.profile = profiles.profile
				join distributions on
					distributions.name = profiles.distro
        order by id desc;


create table if not exists upgrade_requests_table (
	id SERIAL PRIMARY KEY,
	request_hash varchar(30) UNIQUE,
	subtarget_id integer references subtargets_table(id) ON DELETE CASCADE,
	request_manifest_id integer references manifest_table(id) ON DELETE CASCADE,
	response_release_id integer references releases_table(id),
	response_manifest_id integer references manifest_table(id)
);

create or replace view upgrade_requests as
select
upgrade_requests_table.id, request_hash, subtargets.distro, subtargets.release, target, subtarget, reqm.hash request_manifest, releases.release response_release, resm.hash response_manifest
from upgrade_requests_table, subtargets, manifest_table reqm, manifest_table resm, releases where
subtargets.id = upgrade_requests_table.subtarget_id and
reqm.id = request_manifest_id and
resm.id = response_manifest_id and
releases.id = response_release_id;

create or replace rule insert_upgrade_requests AS
ON insert TO upgrade_requests DO INSTEAD
insert into upgrade_requests_table (request_hash, subtarget_id, request_manifest_id, response_release_id, response_manifest_id) values (
	NEW.request_hash,
	(select subtargets.id from subtargets where
		subtargets.distro = NEW.distro and
		subtargets.release = NEW.release and
		subtargets.target = NEW.target and
		subtargets.subtarget = NEW.subtarget),
	(select manifest_table.id from manifest_table where
		manifest_table.hash = NEW.request_manifest),
	(select id from releases where
		releases.distro = NEW.distro and
		releases.release = NEW.response_release),
	(select manifest_table.id from manifest_table where
		manifest_table.hash = NEW.response_manifest)
	)
on conflict do nothing;

create or replace rule update_upgrade_requests AS
ON update TO upgrade_requests DO INSTEAD
update upgrade_requests_table set
response_release_id = coalesce(
	(select id from releases where
		releases.distro = NEW.distro and
		releases.release = NEW.response_release),
	response_release_id),
response_manifest_id = coalesce(
	(select manifest_table.id from manifest_table where
		manifest_table.hash = NEW.response_manifest),
	response_manifest_id)
where upgrade_requests_table.request_hash = NEW.request_hash
returning
old.*; 

