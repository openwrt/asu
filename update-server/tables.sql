create table packages_names (
    id SERIAL PRIMARY KEY,
	name varchar(20) UNIQUE
);

create table releases (
    distro varchar(20),
    release varchar(20),
    PRIMARY KEY (distro, release)
);

create table targets (
    id SERIAL PRIMARY KEY,
    distro varchar(20),
    release varchar(20),
    target varchar(20),
    subtarget varchar(20),
	supported bool DEFAULT false,
    PRIMARY KEY (distro, release, target, subtarget),
    FOREIGN KEY (distro, release) REFERENCES releases
);

create table profiles (
    id SERIAL PRIMARY KEY,
    distro varchar(20),
    release varchar(20),
    target varchar(20),
    subtarget varchar(20),
    name varchar(20),
    board varchar(20),
    PRIMARY KEY(distro, release, target, subtarget, name, board),
    FOREIGN KEY (distro, release, target, subtarget) REFERENCES targets
);

create table target_packages (
	profile INTEGER,
	package INTEGER
	version varchar(20),
    FOREIGN KEY (profile) REFERENCES targets(id),
    FOREIGN KEY (package) REFERENCES packages_names(id)
);

create table profile_packages (
	profile INTEGER,
	package INTEGER
    FOREIGN KEY (profile) REFERENCES profiles(id),
    FOREIGN KEY (package) REFERENCES packages_names(id)
);

create table default_packages (
	target INTEGER,
	package INTEGER
    FOREIGN KEY (target) REFERENCES targets(id),
    FOREIGN KEY (package) REFERENCES packages_names(id)
);

create table packages_hashes (
	hash varchar(20) primary key,
    package INTEGER
    FOREIGN KEY (package) REFERENCES packages_names(id)
);



create table images (
    id SERIAL PRIMARY KEY,
    image_hash varchar(20) UNIQUE,
    distro varchar(20),
    release varchar(20),
    target varchar(20),
    subtarget varchar(20),
    profile varchar(20),
    package_hash varchar(20),
    network_profile varchar(20),
    checksum varchar(20),
	filesize integer,
	build_date timestamp,
	last_download timestamp,
	downloads integer DEFAULT 0,
	keep boolean DEFAULT false,
    status varchar(20) DEFAULT 'requested',
    FOREIGN KEY (distro, release, target, subtarget) REFERENCES targets,
    FOREIGN KEY (package_hash) REFERENCES packages_hashes(hash)
);

create function add_default_packages(distro varchar(20), release varchar(20), target varchar(20), subtarget varchar(20), packages text) returns void as
$$
declare
	packages_array = string_to_array(packages, ' ')
begin
	for package in packages_array
	loop
		insert package into packages_names where not in (select name from packages_names);
		insert into default_packages values(
			(select id from targets where 
				targets.distro = distro,
				targets.release = release,
				targets.target = target,
				targets.subtarget = subtarget), 
			(select id from packages where packages.name = package)
		);
	end loop;
end
$$ language 'plpgsql';

create view get_default_packages as
	select packages.name
	from packages, targets, default_packages
	where 
		default_packages.package = packages.id,
		default_packages.target = targets.id
	;
