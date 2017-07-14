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
		distro, release, target, subtarget, profile
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
	) on conflict do nothing;
end
$$ language 'plpgsql';

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

create table if not exists packages_available(
	subtarget_id integer references subtargets(id),
	package integer references packages_names(id),
	version varchar(30),
	primary key(subtarget_id, package)

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
		insert into profiles values (distro, release, target, subtarget, profile);
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
