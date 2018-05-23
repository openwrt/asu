import datetime
import psycopg2
import logging
import json

from utils.common import get_hash

class Database():
    def __init__(self, config):
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = config
        self.log.info("config initialized")
        connection_string = \
            "dbname='{}' user='{}' host='{}' password='{}' port='{}'".format(
                self.config.get("database_name"),
                self.config.get("database_user"),
                self.config.get("database_address"),
                self.config.get("database_pass"),
                self.config.get("database_port"))
        self.cnxn = psycopg2.connect(connection_string)
        self.c = self.cnxn.cursor()
        self.log.info("database connected")

    def commit(self):
        self.cnxn.commit()

    def fetchone(self, sql, *vars):
        self.c.execute(sql, vars)
        fetch = self.c.fetchone()
        if fetch:
            return fetch[0]
        return None

    def execute(self, sql, *vars):
        self.c.execute(sql, *vars)

    def fetchall(self, sql, *vars):
        self.c.execute(sql, vars)
        return self.c.fetchall()

    def create_tables(self):
        self.log.info("creating tables")
        with open('tables.sql') as t:
            self.execute(t.read())
        self.commit()
        self.log.info("created tables")

    def set_distro_alias(self, distro, alias):
        self.log.info("set alias %s/%s ", distro, alias)
        sql = "UPDATE distributions SET alias = %s WHERE name = %s;"
        self.execute(sql, alias, distro)
        self.commit()

    def insert_release(self, distro, release, alias=""):
        self.log.info("insert %s/%s ", distro, release)
        sql = "INSERT INTO releases (distro, release, alias) VALUES (%s, %s, %s);"
        self.execute(sql, distro, release, alias)
        self.commit()

    def insert_supported(self, distro, release, target, subtarget="%"):
        self.log.info("insert supported {} {} {} {}".format(distro, release, target, subtarget))
        sql = """UPDATE subtargets SET supported = true
            WHERE distro=%s and release=%s and target=%s and subtarget LIKE %s"""
        self.execute(sql, distro, release, target, subtarget)
        self.commit()

    def insert_upgrade_check(self, request_hash, distro, release, target, subtarget, request_manifest, response_release, response_manifest):
        sql = """insert into upgrade_requests
            (request_hash, distro, release, target, subtarget, request_manifest, response_release, response_manifest)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        self.c.execute(sql, request_hash, distro, release, target, subtarget, request_manifest, response_release, response_manifest)
        self.commit()

    def check_distro(self, distro):
        self.execute("select 1 from distributions where name = %s", distro)
        if self.c.rowcount == 1:
            return True
        else:
            return False

    def get_releases(self, distro=None):
        if not distro:
            return self.fetchall("select distro, release from releases")
        else:
            releases = self.fetchall("select release from releases WHERE distro=%s", distro)
            print(releases)
            respond = []
            for release in releases:
                respond.append(release[0])
            return respond

    def insert_hash(self, hash, packages):
        sql = "INSERT INTO packages_hashes (hash, packages) VALUES (%s, %s)"
        self.execute(sql, (hash, " ".join(packages)))
        self.commit()

    def delete_profiles(self, distro, release, target, subtarget, profiles):
        self.log.debug("delete profiles of %s/%s/%s/%s", distro, release, target, subtarget)
        subtarget_id = self.execute("""delete from profiles_table
            where subtarget_id = (select id from subtargets where
            subtargets.distro = %s and
            subtargets.release = %s and
            subtargets.target = %s and
            subtargets.subtarget = %s)""", distro, release, target, subtarget)
        self.commit()

    def insert_profiles(self, distro, release, target, subtarget, packages_default, profiles):

        self.log.debug("insert_profiles %s/%s/%s/%s", distro, release, target, subtarget)
        self.execute("INSERT INTO packages_default VALUES (%s, %s, %s, %s, %s);", distro, release, target, subtarget, packages_default)

        sql = "INSERT INTO packages_profile VALUES (%s, %s, %s, %s, %s, %s, %s);"
        for profile in profiles:
            profile_name, profile_model, profile_packages = profile
            self.log.debug("insert '%s' '%s' '%s'", profile_name, profile_model, profile_packages)
            self.execute(sql, distro, release, target, subtarget, profile_name, profile_model, profile_packages)
        self.commit()

    def check_subtarget(self, distro, release, target, subtarget):
        self.execute("""SELECT 1 from subtargets
            WHERE distro=%s and release=%s and target=%s and subtarget = %s LIMIT 1;""",
            distro, release, target, subtarget)
        if self.c.rowcount == 1:
            return True
        else:
            return False

    def check_profile(self, distro, release, target, subtarget, profile):
        self.log.debug("check_profile %s/%s/%s/%s/%s", distro, release, target, subtarget, profile)
        self.execute("""SELECT profile FROM profiles
            WHERE distro=%s and release=%s and target=%s and subtarget = %s and profile = coalesce(
                (select newname from board_rename where distro = %s and release = %s and target = %s and subtarget = %s and origname = %s), %s)
            LIMIT 1;""",
            distro, release, target, subtarget, distro, release, target, subtarget, profile, profile)
        if self.c.rowcount == 1:
            return self.c.fetchone()[0]
        else:
            return False

    def check_model(self, distro, release, target, subtarget, model):
        self.log.debug("check_model %s/%s/%s/%s/%s", distro, release, target, subtarget, model)
        self.execute("""SELECT profile FROM profiles
            WHERE distro=%s and release=%s and target=%s and subtarget = %s and lower(model) = lower(%s);""",
            distro, release, target, subtarget, model)
        if self.c.rowcount == 1:
            return self.c.fetchone()[0]
        return False

    def get_image_packages(self, distro, release, target, subtarget, profile, as_json=False):
        self.log.debug("get_image_packages for %s/%s/%s/%s/%s", distro, release, target, subtarget, profile)
        sql = "select packages from packages_image where distro = %s and release = %s and target = %s and subtarget = %s and profile = %s"
        response = self.fetchone(sql, distro, release, target, subtarget, profile)
        if response:
            packages = response.rstrip().split(" ")
            if as_json:
                return json.dumps({"packages": packages})
            else:
                return packages
        else:
            return response

    def subtarget_outdated(self, distro, release, target, subtarget):
        outdated_interval = 1
        outdated_unit = 'day'
        sql = """select 1 from subtargets
            where distro = %s and
            release = %s and
            target = %s and
            subtarget = %s and
            last_sync < NOW() - INTERVAL '1 day';"""
        self.execute(sql, distro, release, target, subtarget)
        if self.c.rowcount == 1:
            return True
        else:
            return False

    def get_subtarget_outdated(self):
        sql = """select distro, release, target, subtarget
            from subtargets
            where
            (last_sync < NOW() - INTERVAL '1 day')
            or
            last_sync < '1970-01-02'
            order by (last_sync) asc limit 1;"""
        self.execute(sql)
        if self.c.rowcount == 1:
            return self.c.fetchone()
        else:
            return False

    def subtarget_synced(self, distro, release, target, subtarget):
        sql = """update subtargets set last_sync = NOW()
            where distro = %s and
            release = %s and
            target = %s and
            subtarget = %s;"""
        self.execute(sql, distro, release, target, subtarget)
        self.commit()

    def insert_packages_available(self, distro, release, target, subtarget, packages):
        self.log.debug("insert packages of {}/{}/{}/{}".format(distro, release, target, subtarget))
        sql = """INSERT INTO packages_available VALUES (%s, %s, %s, %s, %s, %s);"""
        for package in packages:
            name, version = package
            self.execute(sql, distro, release, target, subtarget, name, version)
        self.commit()

    def get_packages_available(self, distro, release, target, subtarget):
        self.log.debug("get_available_packages for %s/%s/%s/%s", distro, release, target, subtarget)
        sql = """SELECT name, version FROM packages_available
            WHERE distro=%s and release=%s and target=%s and subtarget=%s;"""
        for name, version in self.fetchall(sql, distro, release, target, subtarget):
            response[name] = version
        return response

    def insert_subtargets(self, distro, release, target, subtargets):
        self.log.info("insert subtargets %s/%s ", target, " ".join(subtargets))
        sql = "INSERT INTO subtargets (distro, release, target, subtarget) VALUES (%s, %s, %s, %s);"
        for subtarget in subtargets:
            self.execute(sql, distro, release, target, subtarget)

        self.commit()

    def get_subtargets(self, distro, release, target="%", subtarget="%"):
        self.log.debug("get_subtargets {} {} {} {}".format(distro, release, target, subtarget))
        sql = """SELECT target, subtarget, supported FROM subtargets WHERE
            distro = %s and release = %s and target LIKE %s and subtarget LIKE
            %s;"""
        return self.fetchall(sql, distro, release, target, subtarget)

    def check_build_request_hash(self, request_hash, status=False):
        self.log.debug("check_request_hash")
        sql = "select image_hash, id, request_hash, status from image_requests where request_hash = %s or image_hash = %s"
        self.c.execute(sql, request_hash, request_hash)
        if self.c.rowcount == 1:
            if not status:
                return self.c.fetchone()
            else:
                return self.c.fetchone()[3]
        else:
            return None

    def check_upgrade_check_hash(self, request_hash):
        self.log.debug("check_upgrade_hash")
        # postgresql is my new crossword puzzle
        sql = """SELECT to_json(sub) AS response
            FROM  (
               SELECT response_release as version, json_object_agg(name, version) AS "packages"
               FROM  upgrade_requests ur
               LEFT JOIN manifest_packages mp ON mp.manifest_hash = ur.response_manifest
               WHERE ur.request_hash = %s
               GROUP BY ur.response_release, ur.response_manifest
               ) sub;
            """
        self.c.execute(sql, request_hash)
        if self.c.rowcount == 1:
            return self.c.fetchone()[0]
        else:
            return None

    def check_build_request(self, request):
        request_array = request.as_array()
        request_hash = get_hash(" ".join(request_array), 12)
        self.log.debug("check_request")
        sql = "select image_hash, id, request_hash, status from image_requests where request_hash = %s"
        self.c.execute(sql, request_hash)
        if self.c.rowcount == 1:
            return self.c.fetchone()
        else:
            self.log.debug("add build job")
            sql = """INSERT INTO image_requests
                (request_hash, distro, release, target, subtarget, profile, packages_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            self.c.execute(sql, request_hash, *request_array)
            self.commit()
            return('', 0, request_hash, 'requested')

    def request_imagebuilder(self, distro, release, target, subtarget):
        sql = """INSERT INTO image_requests
            (distro, release, target, subtarget, status)
            VALUES (%s, %s, %s, %s, %s)"""
        self.c.execute(sql, distro, release, target, subtarget, "imagebuilder")
        self.commit()

    def get_image_path(self, image_hash):
        self.log.debug("get sysupgrade image for %s", image_hash)
        sql = "select file_path from images_download where image_hash = %s"
        self.c.execute(sql, image_hash)
        if self.c.rowcount == 1:
            return self.c.fetchone()[0]
        else:
            return False

    def get_sysupgrade(self, image_hash):
        self.log.debug("get image %s", image_hash)
        sql = "select file_path, file_name from images_download where image_hash = %s"
        self.c.execute(sql, image_hash)
        if self.c.rowcount == 1:
            return self.c.fetchone()
        else:
            return False

    def add_image(self, image_hash, distro, release, target, subtarget, profile, manifest_hash, worker_id, sysupgrade_suffix="", subtarget_in_name="", profile_in_name="", vanilla=False, build_seconds=0):
        sql = """INSERT INTO images
            (image_hash,
            distro,
            release,
            target,
            subtarget,
            profile,
            manifest_hash,
            worker_id,
            sysupgrade_suffix,
            build_date,
            subtarget_in_name,
            profile_in_name,
            vanilla,
            build_seconds)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s)"""
        self.c.execute(sql,
                image_hash,
                distro, release, target, subtarget, profile, manifest_hash,
                worker_id,
                sysupgrade_suffix,
                'true' if subtarget_in_name else 'false', # dirty, outdated pyodbc%s
                'true' if profile_in_name else 'false',
                'true' if vanilla else 'false',
                build_seconds)
        self.commit()

    def add_manifest_packages(self, manifest_hash, packages):
        self.log.debug("add manifest packages")
        sql = """INSERT INTO manifest_table (hash) VALUES (%s) ON CONFLICT DO NOTHING;"""
        self.c.execute(sql, manifest_hash)
        for name, version in packages.items():
            sql = """INSERT INTO manifest_packages (manifest_hash, name, version) VALUES (%s, %s, %s);"""
            self.c.execute(sql, manifest_hash, name, version)
        self.commit()

    def get_build_job(self, distro='%', release='%', target='%', subtarget='%'):
        self.log.debug("get build job %s %s %s %s", distro, release, target, subtarget)
        sql = """UPDATE image_requests
            SET status = 'building'
            FROM packages_hashes
            WHERE image_requests.packages_hash = packages_hashes.hash and
                distro LIKE %s and
                release LIKE %s and
                target LIKE %s and
                subtarget LIKE %s and
                image_requests.id = (
                    SELECT MIN(id)
                    FROM image_requests
                    WHERE status = 'requested' and
                    distro LIKE %s and
                    release LIKE %s and
                    target LIKE %s and
                    subtarget LIKE %s
                )
            RETURNING image_requests.id, image_hash, distro, release, target, subtarget, profile, packages_hashes.packages;"""
        self.c.execute(sql, distro, release, target, subtarget, distro, release, target, subtarget)
        if self.c.description:
            self.log.debug("found image request")
            self.commit()
            return list(self.c.fetchone())
        self.log.debug("no image request")
        return None

    def set_image_requests_status(self, image_request_hash, status):
        self.log.info("set image {} status to {}".format(image_request_hash, status))
        sql = """UPDATE image_requests
            SET status = %s
            WHERE request_hash = %s;"""
        self.c.execute(sql, status, image_request_hash)
        self.commit()

    def worker_done_build(self, request_hash, image_hash, status):
        self.log.info("done build job: rqst %s img %s status %s", request_hash, image_hash, status)
        sql = """UPDATE image_requests SET
            status = %s,
            image_hash = %s
            WHERE request_hash = %s;"""
        self.c.execute(sql, status, image_hash, request_hash)
        self.commit()

    def done_build_job(self, request_hash, image_hash, status="created"):
        self.log.info("done build job: rqst %s img %s status %s", request_hash, image_hash, status)
        sql = """UPDATE image_requests SET
            status = %s,
            image_hash = %s
            WHERE request_hash = %s;"""
        self.c.execute(sql, status, image_hash, request_hash)
        self.commit()

    def imagebuilder_status(self, distro, release, target, subtarget):
        sql = """select 1 from worker_imagebuilder
            WHERE distro=%s and release=%s and target=%s and subtarget=%s;"""
        self.c.execute(sql, distro, release, target, subtarget)
        if self.c.rowcount > 0:
            return "ready"
        else:
            self.log.debug("add imagebuilder request")
            sql = """insert into imagebuilder_requests
                (distro, release, target, subtarget)
                VALUES (%s, %s, %s, %s)"""
            self.c.execute(sql, distro, release, target, subtarget)
            self.commit()
            return 'requested'

    def set_imagebuilder_status(self, distro, release, target, subtarget, status):
        sql = """UPDATE imagebuilder SET status = %s
            WHERE distro=%s and release=%s and target=%s and subtarget=%s"""
        self.c.execute(sql, status, distro, release, target, subtarget)
        self.commit()

    def get_imagebuilder_request(self):
        sql = """UPDATE imagebuilder
            SET status = 'initialize'
            WHERE status = 'requested' and id = (
                SELECT MIN(id)
                FROM imagebuilder
                WHERE status = 'requested'
                )
            RETURNING distro, release, target, subtarget;"""
        self.c.execute(sql)
        if self.c.description:
            self.commit()
            return self.c.fetchone()
        else:
            return None

    def reset_build_requests(self):
        self.log.debug("reset building images")
        sql = "UPDATE image_requests SET status = 'requested' WHERE status = 'building'"
        self.c.execute(sql)
        self.commit()

    def worker_active_subtargets(self):
        self.log.debug("worker active subtargets")
        sql = """select distro, release, target, subtarget from worker_skills_subtargets, subtargets
                where worker_skills_subtargets.subtarget_id = subtargets.id"""
        self.c.execute(sql)
        result = self.c.fetchall()
        return result

    def worker_needed(self, worker=False):
        self.log.debug("get needed worker")
        sql = """(select * from imagebuilder_requests union
            select distro, release, target, subtarget
                from worker_needed, subtargets
                where worker_needed.subtarget_id = subtargets.id) limit 1"""
        result = self.c.execute(sql).fetchone()
        if not worker:
            return result
        else:
            if result:
                return "/".join(result)
            else:
                return ""

    def worker_register(self, name, address, pubkey):
        self.log.info("register worker %s %s", name, address)
        sql = """INSERT INTO worker (name, address, heartbeat, public_key)
            VALUES (%s, %s, %s, %s)
            RETURNING id;"""
        self.c.execute(sql, name, address, datetime.datetime.now(), pubkey)
        self.commit()
        return self.c.fetchone()[0]

    def worker_destroy(self, worker_id):
        self.log.info("destroy worker %s", worker_id)
        sql = """delete from worker where id = %s"""
        self.c.execute(sql, worker_id)
        self.commit()

    def worker_add_skill(self, worker_id, distro, release, target, subtarget, status):
        self.log.info("register worker skill %s %s", worker_id, status)
        sql = """INSERT INTO worker_skills
            select %s, subtargets.id, %s from subtargets
            WHERE distro = %s and release = %s and target LIKE %s and subtarget = %s;
            delete from imagebuilder_requests
            WHERE distro = %s and release = %s and target LIKE %s and subtarget = %s;"""
        self.c.execute(sql, worker_id, status, distro, release, target, subtarget, distro, release, target, subtarget)
        self.commit()

    def worker_heartbeat(self, worker_id):
        self.log.debug("heartbeat %s", worker_id)
        sql = "UPDATE worker SET heartbeat = %s WHERE id = %s"
        self.c.execute(sql, datetime.datetime.now(), worker_id)
        self.commit()

    def get_subtargets_supported(self):
        self.log.debug("get subtargets supported")
        sql = """select distro, release, target,
                string_agg(subtarget, ', ') as subtargets
                from subtargets
                where supported = 'true'
                group by (distro, release, target)
                order by distro, release desc, target"""

        self.c.execute(sql)
        result = self.c.fetchall()
        return result

    def get_supported_distros(self):
        sql = """select
        coalesce(array_to_json(array_agg(row_to_json(distributions))), '[]')
        from (select name, alias from distributions order by (alias)) as
        distributions;"""
        return self.fetchone(sql)

    def get_supported_releases(self, distro):
        if distro == '': distro='%'
        sql = """select
        coalesce(array_to_json(array_agg(row_to_json(releases))), '[]') from
        (select distro, release from releases where distro LIKE %s order by id
                desc) as releases;"""
        return self.fetchone(sql, distro)

    def get_supported_models(self, search='', distro='', release=''):
        search_like = '%' + search.lower() + '%'
        if distro == '': distro = '%'
        if release == '': release = '%'

        sql = """select coalesce(array_to_json(array_agg(row_to_json(profiles))), '[]') from profiles where lower(model) LIKE %s and distro LIKE %s and release LIKE %s;"""
        response = self.c.execute(sql, search_like, distro, release).fetchone()[0]
        if response == "[]":
            sql = """select coalesce(array_to_json(array_agg(row_to_json(profiles))), '[]') from profiles where (lower(target) LIKE %s or lower(subtarget) LIKE %s or lower(profile) LIKE %s)and distro LIKE %s and release LIKE %s;"""
            self.c.execute(sql, search_like, search_like, search_like, distro, release)
            response = self.c.fetchone()[0]

        return response

    def get_subtargets_json(self, distro='%', release='%', target='%'):
        sql = """select coalesce(array_to_json(array_agg(row_to_json(subtargets))), '[]') from subtargets where distro like %s and release like %s and target like %s;"""
        self.c.execute(sql, distro, release, target)
        return self.c.fetchone()[0]

    def get_request_packages(self, distro, release, target, subtarget, profile):
        sql = """select coalesce(array_to_json(array_agg(row_to_json(subtargets))), '[]') from subtargets where distro like %s and release like %s and target like %s;"""


    def get_images_list(self):
        self.log.debug("get images list")
        sql = "select * from images_list"
        self.c.execute(sql)
        result = self.c.fetchall()
        return result

    def get_fails_list(self):
        self.log.debug("get fails list")
        sql = """select distro, release, target, subtarget, profile, request_hash, hash packages_hash, status
            from image_requests_table join profiles on image_requests_table.profile_id = profiles.id join packages_hashes on image_requests_table.packages_hash_id = packages_hashes.id
            where status != 'created' """
        self.c.execute(sql)
        result = self.c.fetchall()
        return result

    def get_image_info(self, image_hash, json=False):
        self.log.debug("get image info %s", image_hash)
        if not json:
            sql = """select * from images_info where image_hash = %s"""
            self.c.execute(sql, image_hash)
            return(dict(zip([column[0] for column in self.c.description], self.c.fetchone())))
        else:
            sql = "select row_to_json(images_info) from images_info where image_hash = %s"
            self.c.execute(sql, image_hash)
            return(self.c.fetchone()[0])

    def get_manifest_info(self, manifest_hash, json=False):
        self.log.debug("get manifest info %s", manifest_hash)
        if not json:
            sql = """select name, version from manifest_packages
                where manifest_hash = %s"""
            self.c.execute(sql, manifest_hash)
            result = self.c.fetchall()
            return result
        else:
            sql = """select json_object_agg(manifest_packages.name, manifest_packages.version) from manifest_packages where manifest_hash = %s;"""
            self.c.execute(sql, manifest_hash)
            return(self.c.fetchone()[0])

    def get_packages_hash(self, packages_hash):
        self.log.debug("get packages_hash %s", packages_hash)
        sql = "select packages from packages_hashes where hash = %s;"
        return self.c.execute(sql, packages_hash).fetchone()[0]

    def get_popular_subtargets(self):
        self.log.debug("get popular subtargets")
        sql = """select count(*) as count, target, subtarget from images
            group by (target, subtarget)
            order by count desc
            limit 10"""
        self.c.execute(sql)
        result = self.c.fetchall()
        return result

    def get_worker_active(self):
        self.log.debug("get worker active")
        sql = "select count(*) as count from worker;"
        self.c.execute(sql)
        result = self.c.fetchone()
        return result[0]

    def get_images_count(self):
        self.log.debug("get images count")
        sql = "select count(*) as count from images;"
        self.c.execute(sql)
        result = self.c.fetchone()
        return result[0]

    def get_images_total(self):
        self.log.debug("get images count")
        sql = "select last_value as total from image_requests_table_id_seq;"
        self.c.execute(sql)
        result = self.c.fetchone()
        return result[0]

    def get_packages_count(self):
        self.log.debug("get packages count")
        sql = "select count(*) as count from packages_names;"
        self.c.execute(sql)
        result = self.c.fetchone()
        return result[0]

    def packages_versions(self, distro, release, target, subtarget, packages):
        self.log.debug("packages versions")
        sql = """
        select name, version from
            unnest(string_to_array(%s, ' ')) packages_installed left join
            (select name, version from packages_available where
            distro = %s and release = %s and target = %s and subtarget = %s) as packages_available
            on packages_available.name = packages_installed;
        """
        self.c.execute(sql, packages, distro, release, target, subtarget)
        result = self.c.fetchall()
        return result

    def packages_updates(self, distro, release, target, subtarget, packages):
        self.log.debug("packages updates")
        sql = """select name, version, installed_version from packages_available join (
                select key as installed_name, value as installed_version from json_each_text(%s)
                ) as installed on installed.installed_name = packages_available.name
        where installed.installed_version != packages_available.version and
            distro = %s and release = %s and target = %s and subtarget = %s"""
        self.c.execute(sql, str(packages).replace("\'", "\""), distro, release, target, subtarget)
        result = self.c.fetchall()
        return result

    def flush_snapshots(self, distro="%", target="%", subtarget="%"):
        self.log.debug("flush snapshots")
        sql = """delete from images where
            distro LIKE %s and
            target LIKE %s and
            subtarget LIKE %s and
            release = 'snapshot';"""
        self.c.execute(sql, distro, target, subtarget)

        sql = """delete from image_requests where
            distro LIKE %s and
            target LIKE %s and
            subtarget LIKE %s and
            release = 'snapshot';"""
        self.c.execute(sql, distro, target, subtarget)

        sql = """update subtargets set last_sync = date('1970-01-01') where
            distro LIKE %s and
            target LIKE %s and
            subtarget LIKE %s and
            release = 'snapshot';"""
        self.c.execute(sql, distro, target, subtarget)
        self.commit()

    def insert_board_rename(self, distro, release, origname, newname):
        sql = "INSERT INTO board_rename (distro, release, origname, newname) VALUES (%s, %s, %s, %s);"
        self.c.execute(sql, distro, release, origname, newname)
        self.commit()

    def insert_transformation(self, distro, release, package, replacement, context):
        self.log.info("insert %s/%s ", distro, release)
        sql = "INSERT INTO transformations (distro, release, package, replacement, context) VALUES (%s, %s, %s, %s, %s);"
        self.c.execute(sql, distro, release, package, replacement, context)
        self.commit()

    def transform_packages(self, distro, orig_release, dest_release, packages):
        self.log.debug("transform packages {} {} {} {}".format(distro, orig_release, dest_release, packages))
        sql = "select transform(%s, %s, %s, %s)"
        self.c.execute(sql, distro, orig_release, dest_release, packages)
        return self.c.fetchall()

    def worker_build_job(self, worker_id):
        self.log.debug("get build job for worker %s", worker_id)
        sql = """UPDATE image_requests
            SET status = 'building'
            FROM packages_hashes
            WHERE image_requests.packages_hash = packages_hashes.hash and
                distro LIKE %s and
                release LIKE %s and
                target LIKE %s and
                subtarget LIKE %s and
                image_requests.id = (
                    SELECT MIN(id)
                    FROM image_requests
                    WHERE status = 'requested' and
                    distro LIKE %s and
                    release LIKE %s and
                    target LIKE %s and
                    subtarget LIKE %s
                )
            RETURNING image_requests.id, image_hash, distro, release, target, subtarget, profile, packages_hashes.packages;"""
        self.c.execute(sql, distro, release, target, subtarget, distro, release, target, subtarget)
        if self.c.description:
            self.log.debug("found image request")
            self.commit()
            return self.c.fetchone()
        self.log.debug("no image request")
        return None

    def get_popular_packages(self):
        sql = """select name, count(name) as count
            from packages_hashes_link phl join packages_names pn
                on phl.package_id = pn.id
            where name not like '-%'
            group by name
            order by count desc;"""
        self.c.execute(sql)
        return self.c.fetchall()

    def get_worker(self, worker_id):
        sql = "select * from worker where id = %s"
        result = self.c.execute(sql, worker_id)
        if self.c.rowcount == 1:
            return self.c.fetchone()
        else:
            return False

