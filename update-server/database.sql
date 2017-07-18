create table if not exists releases(
	distro varchar(20),
	release varchar(20),
	primary key(distro, release)
);

create table if not exists subtargets(
	id serial primary key,
	distro varchar(20),
	release varchar(20),
	target varchar(20),
	subtarget varchar(20),
	unique(distro, release, target, subtarget),
    foreign key (distro, release) references releases
);

create table if not exists profiles_table(
	id serial primary key,
	subtarget_id integer references subtargets(id),
	profile varchar(20),
	unique(subtarget_id, profile)
);

create or replace view profiles as
	select
		profiles_table.id, distro, release, target, subtarget, profile
	from subtargets, profiles_table
	where 
		profiles_table.subtarget_id = subtargets.id
;

create or replace function add_profiles(distro varchar(20), release varchar(20), target varchar(20), subtarget varchar(20), name varchar(20)) returns void as
$$
begin
	insert into profiles_table (subtarget_id, profile) values (
		(select id from subtargets where
			subtargets.distro = add_profiles.distro and
			subtargets.release = add_profiles.release and
			subtargets.target = add_profiles.target and
			subtargets.subtarget = add_profiles.subtarget),
		name
	)  on conflict do nothing;
end
$$ language 'sql';

create or replace rule insert_profiles AS
	ON insert TO profiles DO INSTEAD
		SELECT add_profiles(
			NEW.distro,
			NEW.release,
			NEW.target,
			NEW.subtarget,
			NEW.profile
);

create table if not exists packages_names(
	id serial primary key,
	name varchar(50) unique
);

create table if not exists packages_available_table(
	subtarget_id integer references subtargets(id),
	package integer references packages_names(id),
	version varchar(30),
	primary key(subtarget_id, package)

);

create or replace view packages_available as
	select
		distro, release, target, subtarget, name, version
	from packages_names, subtargets, packages_available_table
	where 
		subtargets.id = packages_available_table.subtarget_id and
		packages_available_table.package = packages_names.id
;

create or replace function add_packages_available(distro varchar(20), release varchar(20), target varchar(20), subtarget varchar(20), name varchar(50), version varchar(30)) returns void as
$$
begin
	insert into packages_names (name) values (add_packages_available.name) on conflict do nothing;
	insert into packages_available_table values (
		(select id from subtargets where
			subtargets.distro = add_packages_available.distro and
			subtargets.release = add_packages_available.release and
			subtargets.target = add_packages_available.target and
			subtargets.subtarget = add_packages_available.subtarget),
		(select id from packages_names where 
			packages_names.name = add_packages_available.name),
		add_packages_available.version
	) on conflict do nothing;
end
$$ language 'sql';

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
	subtarget_id integer references subtargets(id),
	package integer references packages_names(id),
	primary key(subtarget_id, package)
);

create or replace view packages_default as
	select
		distro, release, target, subtarget,
		string_agg(packages_names.name, ' ') as packages
	from subtargets, packages_default_table, packages_names
	where 
		subtargets.id = packages_default_table.subtarget_id and
		packages_default_table.package = packages_names.id
	group by (distro, release, target, subtarget)
;

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
$$ language 'plpgsql';

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
	profile_id integer references profiles_table(id),
	package integer references packages_names(id),
	primary key(profile_id, package)
);

create or replace view packages_profile as
	select
		distro, release, target, subtarget, profile,
		string_agg(packages_names.name, ' ') as packages
	from packages_names, packages_profile_table, subtargets, profiles_table
	where 	
		packages_profile_table.package = packages_names.id and
		packages_profile_table.profile_id = profiles_table.id and
		subtargets.id = profiles_table.subtarget_id
	group by (distro, release, target, subtarget, profile)
;

create or replace function add_packages_profile(distro varchar(20), release varchar(20), target varchar(20), subtarget varchar(20), profile varchar(20), packages text) returns void as
$$
declare
	package varchar(40);
	packages_array varchar(40)[] = string_to_array(packages, ' ');
begin
	FOREACH package IN array packages_array
	loop
		insert into packages_names (name) values (package) on conflict do nothing;
		insert into profiles (distro, release, target, subtarget, profile) 
			values (distro, release, target, subtarget, profile);
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
$$ language 'plpgsql';

create or replace rule insert_packages_profile AS
	ON insert TO packages_profile DO INSTEAD
		SELECT add_packages_profile(
			NEW.distro,
			NEW.release,
			NEW.target,
			NEW.subtarget,
			NEW.profile,
			NEW.packages
);

create table if not exists packages_hashes_table (
	id serial primary key,
	hash text unique
);

create table if not exists packages_hashes_link(
	hash_id integer references packages_hashes_table(id),
	package_id integer references packages_names(id),
	primary key(hash_id, package_id)
);

create or replace view packages_hashes as
	select
		hash, string_agg(packages_names.name, ' ') as packages
	from packages_names, packages_hashes_table, packages_hashes_link
	where
		packages_hashes_table.id = packages_hashes_link.hash_id and
		packages_names.id = packages_hashes_link.package_id
	group by (hash)
;

create or replace function add_packages_hashes(hash varchar(20), packages text) returns void as
$$
declare
	package varchar(40);
	packages_array varchar(40)[] = string_to_array(packages, ' ');
begin
	insert into packages_hashes_table (hash) values (add_packages_hashes.hash) on conflict do nothing;
	FOREACH package IN array packages_array
	loop
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
	)
;

create or replace view packages_image as
	select
		packages_profile.distro, 
		packages_profile.release,
		packages_profile.target,
		packages_profile.subtarget,
		packages_profile.profile, 
		packages_default.packages || ' ' || packages_profile.packages as packages
	from packages_default, packages_profile
	where 
		packages_default.distro = packages_profile.distro AND
		packages_default.release = packages_profile.release AND
		packages_default.target = packages_profile.target AND
		packages_default.subtarget = packages_profile.subtarget
;

create table if not exists imagebuilder_table (
    id SERIAL PRIMARY KEY,
	subtarget_id integer references subtargets(id),
    status varchar(20) DEFAULT 'requested' -- 'ready', 'disabled', 'failded'
);

create or replace view imagebuilder as
	select
		distro, release, target, subtarget, status
	from subtargets, imagebuilder_table
	where 
		subtargets.id = imagebuilder_table.subtarget_id
;

create or replace rule insert_imagebuilder AS
	ON insert TO imagebuilder DO INSTEAD
		insert into imagebuilder_table (subtarget_id)  values (
			(select id from subtargets where
				subtargets.distro = NEW.distro and
				subtargets.release = NEW.release and
				subtargets.target = NEW.target and
				subtargets.subtarget = NEW.subtarget)
		) on conflict do nothing;
;

create table if not exists images_table (
    id SERIAL PRIMARY KEY,
    image_hash text UNIQUE,
	profile_id integer references profiles_table(id),
	packages_hash_id integer references packages_hashes_table(id),
    network_profile text,
    checksum varchar(30),
	filesize integer,
	build_date timestamp,
	last_download timestamp,
	downloads integer DEFAULT 0,
	keep boolean DEFAULT false, -- may used in future
    status text DEFAULT 'requested'
);

create or replace view images as
	select
		image_hash, distro, release, target, subtarget, profile, hash as packages_hash, network_profile, status, checksum, filesize
	from profiles, images_table, packages_hashes_table
	where 
		profiles.id = images_table.profile_id and
		packages_hashes_table.id = images_table.packages_hash_id
;

create or replace rule insert_images AS
	ON insert TO images DO INSTEAD
		insert into images_table (image_hash, profile_id, packages_hash_id, network_profile, checksum, filesize) values (
			NEW.image_hash,
			(select profiles.id from profiles where
				profiles.distro = NEW.distro and
				profiles.release = NEW.release and
				profiles.target = NEW.target and
				profiles.subtarget = NEW.subtarget),
			(select packages_hashes_table.id from packages_hashes_table where
				packages_hashes_table.hash = NEW.packages_hash),
			NEW.network_profile,
			NEW.checksum,
			NEW.filesize
		) on conflict do nothing;
;
