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

create table if not exists profiles(
	id serial primary key,
	subtarget_id integer references subtargets(id),
	profile varchar(20),
	unique(subtarget_id, profile)
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
