create table releases (
    distro text,
    release text,
    PRIMARY KEY (distro, release)
);

create table targets (
    id SERIAL PRIMARY KEY,
    distro text,
    release text,
    target text,
    subtarget text,
	supported bool DEFAULT false,
    PRIMARY KEY (distro, release, target, subtarget),
    FOREIGN KEY (distro, release) REFERENCES releases
);

create table profiles (
    id SERIAL PRIMARY KEY,
    distro text,
    release text,
    target text,
    subtarget text,
    name text,
    board text,
    PRIMARY KEY(distro, release, target, subtarget, name, board),
    FOREIGN KEY (distro, release, target, subtarget) REFERENCES targets
);

create table target_packages (
	profile INTEGER,
	package INTEGER
	version text,
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
	hash text primary key,
    package INTEGER
    FOREIGN KEY (package) REFERENCES packages_names(id)
);

create table packages_names (
    id SERIAL PRIMARY KEY,
	name text UNIQUE
);


create table images (
    id SERIAL PRIMARY KEY,
    image_hash text UNIQUE,
    distro text,
    release text,
    target text,
    subtarget text,
    profile text,
    package_hash text,
    network_profile text,
    checksum text,
	filesize integer,
	build_date timestamp,
	last_download timestamp,
	downloads integer DEFAULT 0,
	keep boolean DEFAULT false,
    status text DEFAULT 'requested',
    FOREIGN KEY (distro, release, target, subtarget) REFERENCES targets,
    FOREIGN KEY (package_hash) REFERENCES packages_hashes(hash)
);
