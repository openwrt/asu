from re import sub
import pyodbc
import logging
import json
import os.path


class Database:
    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = config
        self.log.info("config initialized")
        self.connect()

    def connect(self):
        connection_string = (
            "DRIVER={};".format(self.config.get("database_type"))
            + "SERVER={};".format(self.config.get("database_address"))
            + "DATABASE=asu;"
            + "UID={};".format(self.config.get("database_user"))
            + "PWD={};".format(self.config.get("database_pass"))
            + "PORT={};".format(self.config.get("database_port"))
            + "BoolsAsChar=0"
        )
        self.cnxn = pyodbc.connect(connection_string)
        self.cnxn.autocommit = True
        self.c = self.cnxn.cursor()
        self.c.fast_executemany = True
        self.log.info("database connected")
        return True

    def commit(self):
        self.cnxn.commit()

    def init_db(self):
        self.log.info("database init")
        utils_folder = os.path.dirname(os.path.abspath(__file__))
        with open(utils_folder + "/tables.sql", "r") as tables_file:
            self.c.execute(tables_file.read())
        self.log.info("database init successful")

    def reset_db(self):
        self.c.execute("drop schema public cascade; create schema public;")

    def insert_target(self, distro, version, targets):
        sql = "insert into targets (distro, version, target) values (?, ?, ?);"
        self.cnxn.autocommit = False
        self.c.executemany(
            sql, list(map(lambda target: (distro, version, target), targets))
        )
        self.commit()
        self.cnxn.autocommit = True

    def insert_defaults(self, defaults_hash, defaults):
        sql = """insert into defaults_table (defaults_hash, content)
            values (?, ?) on conflict do nothing"""
        self.c.execute(sql, defaults_hash, defaults)

    def get_defaults(self, defaults_hash):
        sql = "select content from defaults_table where defaults_hash = ?"
        self.c.execute(sql, defaults_hash)
        return self.c.fetchval()

    def insert_supported(self, p):
        sql = """UPDATE targets SET supported = true
            WHERE distro=? and version=? and target=?"""
        self.c.execute(sql, p["distro"], p["version"], p["target"])

    def get_versions(self, distro=None):
        if not distro:
            return self.c.execute("select distro, version from versions").fetchall()
        else:
            versions = self.c.execute(
                "select version from versions WHERE distro=?", (distro,)
            ).fetchall()
            respond = []
            for version in versions:
                respond.append(version[0])
            return respond

    # TODO this should be done via some postgres json magic
    # currently this is splitted back and forth but I'm hungry
    def insert_packages_hash(self, packages_hash, packages):
        sql = """insert into packages_hashes
            (packages_hash, package_name) values (?, ?);"""
        self.cnxn.autocommit = False
        self.c.executemany(
            sql, list(map(lambda package_name: (packages_hash, package_name), packages))
        )
        self.commit()
        self.cnxn.autocommit = True

    def insert_revision(self, distro, version, target, revision):
        sql = """update targets set revisoin = ? where
            distro = ? and version = ? and target = ?;"""
        self.c.execute(sql, revision, distro, version, target)

    def insert_profiles(self, distro, version, target, packages_default, profiles):
        # delete existing packages_default
        sql = """delete from packages_default where
            distro = ? and version = ? and target = ?"""
        self.c.execute(sql, distro, version, target)

        sql = """insert into packages_default
            (distro, version, target, package_name) values (?, ?, ?, ?);"""

        self.cnxn.autocommit = False
        self.c.executemany(
            sql,
            list(
                map(
                    lambda package_name: (distro, version, target, package_name),
                    packages_default,
                )
            ),
        )
        self.commit()
        self.cnxn.autocommit = True

        # delete existing packages_profile
        sql = """delete from packages_profile where
            distro = ? and version = ? and target = ?"""
        self.c.execute(sql, distro, version, target)

        self.cnxn.autocommit = False
        sql = """select insert_packages_profile (?, ?, ?, ?, ?, ?);"""
        self.c.executemany(
            sql,
            list(
                map(
                    lambda profile: (
                        distro,
                        version,
                        target,
                        profile[0],
                        profile[1],
                        profile[2],
                    ),
                    profiles,
                )
            ),
        )
        self.commit()
        self.cnxn.autocommit = True

    def check_packages(self, image):
        sql = """select value as packages_unknown
            from json_array_elements_text(?) as pr
            where not exists (
                select 1 from packages_available pa where
                    pa.distro = ? and
                    pa.version = ? and
                    pa.target = ? and
                    pa.package_name = pr)"""
        # the re.sub() replaces leading - which may appear in package request
        # to explicitly remove packages installed per default
        self.c.execute(
            sql,
            json.dumps([sub(r"^-?", "", p) for p in image["packages"]]),
            image["distro"],
            image["version"],
            image["target"],
        )
        return self.as_array()

    def sysupgrade_supported(self, image):
        self.c.execute(
            """SELECT supported from targets
                WHERE distro=? and version=? and target=? LIMIT 1;""",
            image["distro"],
            image["version"],
            image["target"],
        )
        return self.c.fetchval()

    def check_profile(self, distro, version, target, profile):
        self.log.debug("check_profile %s/%s/%s/%s", distro, version, target, profile)
        self.c.execute(
            """SELECT profile FROM profiles
            WHERE distro=? and version=? and target=? and profile = coalesce(
                (select newname from board_rename
                    where distro = ? and version = ? and
                        target = ? and origname = ?), ?)
            LIMIT 1;""",
            distro,
            version,
            target,
            distro,
            version,
            target,
            profile,
            profile,
        )
        return self.c.fetchval()

    def check_model(self, distro, version, target, model):
        self.log.debug("check_model %s/%s/%s/%s", distro, version, target, model)
        self.c.execute(
            """SELECT profile FROM profiles
                WHERE distro=? and version=? and target=? and
                    lower(model) = lower(?);""",
            distro,
            version,
            target,
            model,
        )
        return self.c.fetchval()

    def get_packages_image(self, request, as_json=False):
        sql = "select packages_image(?, ?, ?, ?);"
        self.c.execute(
            sql,
            request["distro"],
            request["version"],
            request["target"],
            request["profile"],
        )
        return self.as_array()

    # removes an image entry based on image_hash
    def del_image(self, image_hash):
        sql = """delete from images where image_hash = ?;"""
        self.c.execute(sql, image_hash)

    # removes all snapshot requests older than a day
    def del_outdated_request(self,):
        self.c.execute(
            """delete from requests where
            snapshots = 'true' and request_date < NOW() - interval '1 day'"""
        )

    # TODO reimplement
    def get_outdated_manifests(self):
        sql = """select image_hash, files from images join
            manifest_upgrades using (distro, version, target, manifest_hash);"""
        self.c.execute(sql)
        return self.c.fetchall()

    def get_outdated_snapshots(self):
        sql = """select image_hash, files from images where
            snapshots = 'true' and build_date < NOW() - INTERVAL '1 day';"""
        self.c.execute(sql)
        return self.c.fetchall()

    def get_outdated_customs(self):
        sql = """select image_hash, files from images where
            defaults_hash != '' and build_date < NOW() - INTERVAL '7 day';"""
        self.c.execute(sql)
        return self.c.fetchall()

    def get_manifest_upgrades(self, p):
        sql = "select manifest_upgrades(?, ?, ?, ?)"
        self.c.execute(
            sql, p["distro"], p["version"], p["target"], json.dumps(p["manifest"])
        )
        return self.c.fetchval() or "{}"

    def get_outdated_target(self):
        self.c.execute("select * from outdated_target()")
        return self.as_dict()

    def insert_packages_available(self, distro, version, target, packages):
        self.cnxn.autocommit = False
        sql = """insert into packages_available(
            distro, version, target, package_name, package_version)
            values (?, ?, ?, ?, ?);"""
        self.c.executemany(
            sql,
            list(
                map(
                    lambda package: (distro, version, target, package[0], package[1]),
                    packages,
                )
            ),
        )
        self.commit()
        self.cnxn.autocommit = True

    def get_packages_available(self, distro, version, target):
        self.log.debug("get_available_packages for %s/%s/%s", distro, version, target)
        self.c.execute(
            """SELECT name, version
            FROM packages_available
            WHERE distro=? and version=? and target=?;""",
            distro,
            version,
            target,
        )
        response = {}
        for name, version in self.c.fetchall():
            response[name] = version
        return response

    def get_targets(self, distro, version, target="%"):
        self.log.debug("get_targets {} {} {}".format(distro, version, target))
        return self.c.execute(
            """SELECT target, supported FROM targets
            WHERE distro = ? and version = ? and target LIKE ?;""",
            distro,
            version,
            target,
        ).fetchall()

    # check for image_hash or request_hash depending on length
    # TODO make it less confusing
    def check_request_hash(self, request_hash):
        self.log.debug("check_build_request_hash request_hash")
        sql = "select * from requests where request_hash = ?"
        self.c.execute(sql, request_hash)
        return self.as_dict()

    # inserts an image to the build queue
    def add_build_job(self, image):
        self.log.info("add build job %s", image)
        if "packages" in image:
            image.pop("packages")
        self.insert_dict("requests", image)

    # merge image_download table with images tables
    def get_image_path(self, image_hash):
        self.log.debug("get sysupgrade image for %s", image_hash)
        sql = "select * from images where image_hash = ?"
        self.c.execute(sql, image_hash)
        return self.as_dict()

    def as_array(self):
        return list(map(lambda x: x[0], self.c.fetchall()))

    # https://github.com/mkleehammer/pyodbc/issues/171
    def as_dict(self):
        if self.c.rowcount == 1:
            response = dict(
                zip([column[0] for column in self.c.description], self.c.fetchone())
            )
            self.log.debug(response)
            return response
        else:
            return {}

    # this is dangerours if used for user input. check all everything before
    # calling this
    def insert_dict(self, table, data, commit=True):
        columns = []
        values = []
        for key, value in data.items():
            columns.append(key)
            values.append(value)
        sql = "insert into {} ({}) values ({})".format(
            table, ", ".join(columns), "?" + ",?" * (len(values) - 1)
        )
        self.c.execute(sql, values)
        if commit:
            self.commit()

    def add_manifest_packages(self, manifest_hash, packages):
        self.log.debug("add manifest packages")
        self.cnxn.autocommit = False
        sql = """insert into manifest_packages (manifest_hash, package_name, package_version)
            values (?, ?, ?);"""
        self.c.executemany(
            sql,
            list(
                map(lambda package: (manifest_hash, package[0], package[1]), packages)
            ),
        )
        self.commit()
        self.cnxn.autocommit = True

    def get_build_job(self):
        self.c.execute("select * from get_build_job()")
        return self.as_dict()

    def cache_hit(self, image_hash):
        self.log.debug("cache hit for %s", image_hash)
        sql = """UPDATE images SET cache_hits = cache_hits + 1
                WHERE image_hash = ?;"""
        self.c.execute(sql, image_hash)

    def set_requests_status(self, image_request_hash, status):
        self.log.info("set request {} status to {}".format(image_request_hash, status))
        sql = "UPDATE requests SET request_status = ? WHERE request_hash = ?;"
        self.c.execute(sql, status, image_request_hash)

    def done_build_job(self, request_hash, image_hash, status="created"):
        self.log.info(
            "done build job: rqst %s img %s status %s", request_hash, image_hash, status
        )
        sql = """UPDATE requests SET request_status = ?, image_hash = ?
            WHERE request_hash = ?;"""
        self.c.execute(sql, status, image_hash, request_hash)

    def api_get_distros(self):
        sql = """select coalesce(array_to_json(
            array_agg(row_to_json(distributions))), '[]')
                from (select * from distributions order by (alias))
                as distributions;"""
        return self.c.execute(sql).fetchval()

    def api_get_versions(self):
        sql = """select coalesce(array_to_json(array_agg(
            row_to_json(versions))), '[]') from (select * from versions
            order by (alias)) as versions;"""
        return self.c.execute(sql).fetchval()

    def get_supported_models_json(self, search="", distro="", version=""):
        search_like = "%" + search.lower() + "%"
        if distro == "":
            distro = "%"
        if version == "":
            version = "%"
        sql = """select coalesce(array_to_json(array_agg(
            row_to_json(profiles))), '[]') from profiles where
                lower(model) LIKE ? and distro LIKE ? and version LIKE ?;"""
        return self.c.execute(sql, search_like, distro, version).fetchval()

    def get_supported_targets_json(self):
        sql = """select coalesce(array_to_json(array_agg(
            row_to_json(targets))), '[]') from targets where
            supported = 'true';"""
        self.c.execute(sql)
        return self.c.fetchval()

    def get_image_info(self, image_hash):
        self.log.debug("get image info %s", image_hash)
        sql = "select row_to_json(images) from images where image_hash = ?"
        return self.c.execute(sql, image_hash).fetchval()

    def get_manifest_info(self, manifest_hash, json=False):
        self.log.debug("get manifest info %s", manifest_hash)
        sql = """select json_object_agg(
            manifest_packages.package_name,
            manifest_packages.package_version
            ) from manifest_packages where manifest_hash = ?;"""
        self.c.execute(sql, manifest_hash)
        return self.c.fetchval()

    def get_packages_hash(self, packages_hash):
        self.log.debug("get packages_hash %s", packages_hash)
        sql = "select package_name from packages_hashes where packages_hash = ?;"
        self.c.execute(sql, packages_hash)
        return self.as_array()

    def get_popular_targets(self):
        sql = """select json_agg(popular_targets) from (
                select
                    count(*) as count,
                    avg(build_seconds)::integer as build_seconds, target
                from images
                group by (target)
                order by count desc
                limit 50
            ) as popular_targets;"""
        self.c.execute(sql)
        return self.c.fetchval()

    def get_image_stats(self):
        self.log.debug("get image stats")
        sql = """select to_json(image_stats) from
                    (select total, stored, requested from
                        (select last_value as total from
                            images_table_image_id_seq) as total,
                        (select count(*) as stored from images) as stored,
                        (select count(*) as requested from requests where
                            request_status = 'requested') as requested)
                    as image_stats;"""
        return self.c.execute(sql).fetchval()

    def get_all_profiles(self, distro, version):
        sql = """select target, profile from profiles where
            distro = ? and version = ?"""
        self.c.execute(sql, distro, version)
        return self.c.fetchall()

    # get latest 50 images created
    def get_images_latest(self):
        sql = """select json_agg(images_latest) from
            (select * from images where
                defaults_hash is null
                order by image_id desc limit 50)
            as images_latest;"""
        self.c.execute(sql)
        return self.c.fetchval()

    # get latest 50 images failed to build
    def get_fails_latest(self):
        sql = """select json_agg(fails_latest) from
            (select * from requests where
                request_status != 'created' and
                request_status != 'requested' and
                request_status != 'building' and
                request_status != 'no_sysupgrade' and
                defaults_hash is null
                order by request_id desc limit 50)
            as fails_latest;"""
        self.c.execute(sql)
        return self.c.fetchval()

    def get_packages_count(self):
        self.log.debug("get packages count")
        sql = "select count(*) as count from packages_names;"
        self.c.execute(sql)
        return self.c.fetchval()

    def insert_board_rename(self, distro, version, origname, newname):
        sql = """INSERT INTO board_rename (distro, version, origname, newname)
            VALUES (?, ?, ?, ?);"""
        self.c.execute(sql, distro, version, origname, newname)

    def insert_transformation(self, distro, version, package, replacement, context):
        self.log.info("insert %s/%s ", distro, version)
        sql = """INSERT INTO transformations
            (distro, version, package, replacement, context) VALUES
            (?, ?, ?, ?, ?);"""
        self.c.execute(sql, distro, version, package, replacement, context)

    def image_exists(self, image_hash):
        return self.c.execute(
            "select 1 from images where image_hash = ?", image_hash
        ).fetchone()

    def transform_packages(self, distro, orig_version, dest_version, packages):
        sql = "select transform(?, ?, ?, ?)"
        self.c.execute(sql, distro, orig_version, dest_version, packages)
        return self.as_array()

    def get_popular_packages(self):
        sql = """select json_agg(popular_packages) from (select package_name,
        count(package_name) as count from packages_hashes_link phl join
        packages_names pn on phl.package_id = pn.id group by package_name order
        by count desc limit 50) as popular_packages;"""
        self.c.execute(sql)
        return self.c.fetchval()
