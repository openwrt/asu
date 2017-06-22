create table if not exists packages_hashes (
	hash text primary key,
    packages text
);

create table if not exists releases (
    distro text,
    release text,
    PRIMARY KEY (distro, release)
);

create table if not exists targets (
    distro text,
    release text,
    target text,
    subtarget text,
	supported bool,
    PRIMARY KEY (distro, release, target, subtarget),
    FOREIGN KEY (distro, release) REFERENCES releases
);

create table if not exists packages (
    distro text,
    release text,
    target text,
    subtarget text,
    name text,
    version text,
    FOREIGN KEY (distro, release, target, subtarget) REFERENCES targets
);

create table if not exists profiles (
    distro text,
    release text,
    target text,
    subtarget text,
    name text,
    board text,
    packages text,
    PRIMARY KEY(distro, release, target, subtarget, name, board),
    FOREIGN KEY (distro, release, target, subtarget) REFERENCES targets
);

create table if not exists default_packages (
    distro text,
    release text,
    target text,
    subtarget text,
    packages text,
    PRIMARY KEY (distro, release, target, subtarget),
    FOREIGN KEY (distro, release, target, subtarget) REFERENCES targets
);

create table if not exists build_queue (
    id SERIAL PRIMARY KEY,
    image_hash text UNIQUE,
    distro text,
    release text,
    target text,
    subtarget text,
    profile text,
    packages text,
    network_profile text,
    status integer DEFAULT 0,
    FOREIGN KEY (distro, release, target, subtarget) REFERENCES targets
)
