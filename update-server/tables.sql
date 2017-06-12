create table if not exists packages_hashes (
	hash text primary key,
	packages text
);

create table if not exists packages (
	name text,
	version text,
	size integer,
	target text, 
	subtarget text,
	PRIMARY KEY (name, target, subtarget)
);

create table if not exists profiles (
	name text,
	target text,
	subtarget text,
	board text,
	packages text,
	PRIMARY KEY(name, board, target, subtarget)
);

create table if not exists default_packages (
	target text,
	subtarget text,
	packages text,
	PRIMARY KEY (target, subtarget)
);

create table if not exists targets (
	target text,
	subtarget text,
	PRIMARY KEY (target, subtarget)
);

create table if not exists build_queue (
	id SERIAL PRIMARY KEY,
	image_hash text UNIQUE,
	distro text,
	version text,
	target text,
	subtarget text,
	profile text,
	packages text,
	network_profile text,
	status integer DEFAULT 0
)

