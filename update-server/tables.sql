create table if not exists packages_hashes (
	id integer not null primary key,
	hash text,
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
	PRIMARY KEY(name, board)
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
