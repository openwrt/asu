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
    PRIMARY KEY (distro, release, target, subtarget),
    FOREIGN KEY (distro, release) REFERENCES releases
);


create table if not exists packages (
    name text,
    version text,
    distro text,
    release text,
    target text,
    subtarget text,
    FOREIGN KEY (distro, release) REFERENCES releases,
    FOREIGN KEY (target, subtarget) REFERENCES targets
);

create table if not exists profiles (
    name text,
    distro text,
    release text,
    board text,
    target text,
    subtarget text,
    packages text,
    PRIMARY KEY(name, board, target, subtarget),
    FOREIGN KEY (distro, release) REFERENCES releases,
    FOREIGN KEY (target, subtarget) REFERENCES targets
);

create table if not exists default_packages (
    target text,
    subtarget text,
    packages text,
    PRIMARY KEY (target, subtarget),
    FOREIGN KEY (target, subtarget) REFERENCES targets
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
    FOREIGN KEY (distro, release) REFERENCES releases,
    FOREIGN KEY (target, subtarget) REFERENCES targets
)

