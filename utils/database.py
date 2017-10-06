import datetime
import pyodbc
import logging

from utils.common import get_hash
from utils.config import Config

class Database():
    def __init__(self):
        # python3 immport pyodbc; pyodbc.drivers()
        #self.cnxn = pyodbc.connect("DRIVER={SQLite3};SERVER=localhost;DATABASE=test.db;Trusted_connection=yes")
        self.log = logging.getLogger(__name__)
        self.log.info("log initialized")
        self.config = Config()
        self.log.info("config initialized")
        connection_string = "DRIVER={};SERVER={};DATABASE={};UID={};PWD={};PORT={}".format(
                self.config.get("database_type"), self.config.get("database_address"), self.config.get("database_name"), self.config.get("database_user"),
                self.config.get("database_pass"), self.config.get("database_port"))
        self.cnxn = pyodbc.connect(connection_string)
        self.c = self.cnxn.cursor()
        self.log.info("database connected")

    def commit(self):
        self.cnxn.commit()

    def create_tables(self):
        self.log.info("creating tables")
        with open('tables.sql') as t:
            self.c.execute(t.read())
        self.commit()
        self.log.info("created tables")

    def insert_release(self, distro, release):
        self.log.info("insert %s/%s ", distro, release)
        sql = "INSERT INTO releases (distro, release) VALUES (?, ?);"
        self.c.execute(sql, distro, release)
        self.commit()

    def insert_supported(self, distro, release, target, subtarget="%"):
        self.log.info("insert supported {} {} {} {}".format(distro, release, target, subtarget))
        sql = """UPDATE subtargets SET supported = true
            WHERE distro=? and release=? and target=? and subtarget LIKE ?"""
        self.c.execute(sql, distro, release, target, subtarget)
        self.commit()

    def get_releases(self, distro=None):
        if not distro:
            return self.c.execute("select distro, release from releases").fetchall()
        else:
            releases = self.c.execute("select release from releases WHERE distro=?", (distro, )).fetchall()
            respond = []
            for release in releases:
                respond.append(release[0])
            return respond

    def insert_hash(self, hash, packages):
        sql = "INSERT INTO packages_hashes VALUES (?, ?)"
        self.c.execute(sql, (hash, " ".join(packages)))
        self.commit()

    def insert_profiles(self, distro, release, target, subtarget, packages_default, profiles):
        self.log.debug("insert_profiles %s/%s/%s/%s", distro, release, target, subtarget)
        self.c.execute("INSERT INTO packages_default VALUES (?, ?, ?, ?, ?);", distro, release, target, subtarget, packages_default)

        sql = "INSERT INTO packages_profile VALUES (?, ?, ?, ?, ?, ?, ?);"
        for profile in profiles:
            profile_name, profile_model, profile_packages = profile
            self.log.debug("insert '%s' '%s' '%s'", profile_name, profile_model, profile_packages)
            self.c.execute(sql, distro, release, target, subtarget, profile_name, profile_model, profile_packages)
        self.commit()

    def check_profile(self, distro, release, target, subtarget, profile):
        self.log.debug("check_profile %s/%s/%s/%s/%s", distro, release, target, subtarget, profile)
        self.c.execute("""SELECT profile FROM profiles
            WHERE distro=? and release=? and target=? and subtarget = ? and profile = ?
            LIMIT 1;""",
            distro, release, target, subtarget, profile)
        if self.c.rowcount == 1:
            return self.c.fetchone()[0]
        else:
            self.log.debug("use wildcard profile search")
            profile = '%' + profile
            self.c.execute("""SELECT profile FROM profiles
                WHERE distro=? and release=? and target=? and subtarget = ? and profile LIKE ?
                LIMIT 1;""",
                distro, release, target, subtarget, profile)
            if self.c.rowcount == 1:
                return self.c.fetchone()[0]
        return False

    def check_model(self, distro, release, target, subtarget, model):
        self.log.debug("check_model %s/%s/%s/%s/%s", distro, release, target, subtarget, model)
        self.c.execute("""SELECT profile FROM profiles
            WHERE distro=? and release=? and target=? and subtarget = ? and model = ?;""",
            distro, release, target, subtarget, model)
        if self.c.rowcount == 1:
            return self.c.fetchone()[0]
        return False

    def get_profile_packages(self, distro, release, target, subtarget, profile):
        self.log.debug("get_profile_packages for %s/%s/%s/%s/%s", distro, release, target, subtarget, profile)
        self.c.execute("""select packages from packages_image
                where distro = ? and release = ? and target = ? and subtarget = ? and profile = ?""",
            distro, release, target, subtarget, profile)
        response = self.c.fetchone()
        if response:
            return response[0].rstrip().split(" ")
        return response

    def insert_packages_available(self, distro, release, target, subtarget, packages):
        self.log.info("insert packages of %s/%s ", target, subtarget)
        sql = """INSERT INTO packages_available VALUES (?, ?, ?, ?, ?, ?);"""
        for package in packages:
            name, version = package
            self.c.execute(sql, distro, release, target, subtarget, name, version)
        self.commit()

    def get_packages_available(self, distro, release, target, subtarget):
        self.log.debug("get_available_packages for %s/%s/%s/%s", distro, release, target, subtarget)
        self.c.execute("""SELECT name, version
            FROM packages_available
            WHERE distro=? and release=? and target=? and subtarget=?;""",
            distro, release, target, subtarget)
        response = {}
        for name, version in self.c.fetchall():
            response[name] = version
        return response

    def insert_subtargets(self, distro, release, target, subtargets):
        self.log.info("insert subtargets %s/%s ", target, " ".join(subtargets))
        sql = "INSERT INTO subtargets (distro, release, target, subtarget) VALUES (?, ?, ?, ?);"
        for subtarget in subtargets:
            self.c.execute(sql, distro, release, target, subtarget)

        self.commit()

    def get_subtargets(self, distro, release, target="%", subtarget="%"):
        self.log.debug("get_targets {} {} {} {}".format(distro, release, target, subtarget))
        return self.c.execute("""SELECT target, subtarget, supported FROM subtargets
            WHERE
                distro = ? and
                release = ? and
                target LIKE ? and
                subtarget LIKE ?;""",
            distro, release, target, subtarget).fetchall()

    def check_request(self, request):
        self.log.debug("check_request")
        request_array = request.as_array()
        request_hash = get_hash(" ".join(request_array), 12)
        sql = """select id, request_hash, status from image_requests
            where request_hash = ?"""
        self.c.execute(sql, request_hash)
        if self.c.rowcount > 0:
            return self.c.fetchone()
        else:
            self.log.debug("add build job")
            sql = """INSERT INTO image_requests
                (request_hash, distro, release, target, subtarget, profile, packages_hash, network_profile)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
            self.c.execute(sql, request_hash, *request_array)
            self.commit()
            return(0, '', 'requested')

    def request_imagebuilder(self, distro, release, target, subtarget):
        sql = """INSERT INTO image_requests
            (distro, release, target, subtarget, status)
            VALUES (?, ?, ?, ?, ?)"""
        self.c.execute(sql, distro, release, target, subtarget, "imagebuilder")
        self.commit()

    def get_image(self, image_id):
        self.log.debug("get image %s", image_id)
        sql = "select filename, checksum, filesize from images_download, image_requests where image_requests.id = ? and image_requests.image_hash = images_download.image_hash"
        self.c.execute(sql, image_id)
        if self.c.rowcount > 0:
            return self.c.fetchone()
        else:
            return False

    def add_image(self, image_hash, image_array, checksum, filesize):
        self.log.debug("add image %s", image_array)
        sql = """INSERT INTO images
            (image_hash, distro, release, target, subtarget, profile, manifest_hash, network_profile, checksum, filesize, build_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        self.c.execute(sql, image_hash, *image_array, checksum, filesize, datetime.datetime.now())
        self.commit()
        sql = """select id from images where image_hash = ?"""
        self.c.execute(sql, image_hash)
        if self.c.rowcount > 0:
            return self.c.fetchone()[0]
        else:
            return False

    def add_manifest(self, manifest_hash):
        sql = """INSERT INTO manifest_table (hash) VALUES (?) ON CONFLICT DO NOTHING;"""
        self.c.execute(sql, manifest_hash)
        self.commit()
        sql = """select id from manifest_table where hash = ?;"""
        self.c.execute(sql, manifest_hash)
        return self.c.fetchone()[0]

    def add_manifest_packages(self, manifest_hash, packages):
        self.log.debug("add manifest packages")
        for package in packages:
            name, version = package
            sql = """INSERT INTO manifest_packages (manifest_hash, name, version) VALUES (?, ?, ?);"""
            self.c.execute(sql, manifest_hash, name, version)
        self.commit()

    def get_build_job(self, distro='%', release='%', target='%', subtarget='%'):
        self.log.debug("get build job %s %s %s %s", distro, release, target, subtarget)
        sql = """UPDATE image_requests
            SET status = 'building'
            FROM packages_hashes
            WHERE image_requests.packages_hash = packages_hashes.hash and
                distro LIKE ? and
                release LIKE ? and
                target LIKE ? and
                subtarget LIKE ? and
                id = (
                    SELECT MIN(id)
                    FROM image_requests
                    WHERE status = 'requested' and
                    distro LIKE ? and
                    release LIKE ? and
                    target LIKE ? and
                    subtarget LIKE ?
                )
            RETURNING id, image_hash, distro, release, target, subtarget, profile, packages_hashes.packages, network_profile;"""
        self.c.execute(sql, distro, release, target, subtarget, distro, release, target, subtarget)
        if self.c.description:
            self.log.debug("found image request")
            self.commit()
            return self.c.fetchone()
        self.log.debug("no image request")
        return None

    def set_image_requests_status(self, image_request_hash, status):
        sql = """UPDATE image_requests
            SET status = ?
            WHERE image_hash = ?;"""
        self.c.execute(sql, status, image_request_hash)
        self.commit()

    def done_build_job(self, request_hash, image_hash):
        self.log.info("done build job: rqst %s img %s", request_hash, image_hash)
        sql = """UPDATE image_requests SET
            status = 'created',
            image_hash = ?
            WHERE request_hash = ?;"""
        self.c.execute(sql, image_hash, request_hash)
        self.commit()

    def imagebuilder_status(self, distro, release, target, subtarget):
        sql = """select 1 from worker_imagebuilder
            WHERE distro=? and release=? and target=? and subtarget=?;"""
        self.c.execute(sql, distro, release, target, subtarget)
        if self.c.rowcount > 0:
            return "ready"
        else:
            self.log.debug("add imagebuilder request")
            sql = """insert into imagebuilder_requests
                (distro, release, target, subtarget)
                VALUES (?, ?, ?, ?)"""
            self.c.execute(sql, distro, release, target, subtarget)
            self.commit()
            return 'requested'

    def set_imagebuilder_status(self, distro, release, target, subtarget, status):
        sql = """UPDATE imagebuilder SET status = ?
            WHERE distro=? and release=? and target=? and subtarget=?"""
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

    def worker_needed(self):
        self.log.info("get needed worker")
        sql = """(select * from imagebuilder_requests union
            select distro, release, target, subtarget
                from worker_needed, subtargets
                where worker_needed.subtarget_id = subtargets.id) limit 1"""
        self.c.execute(sql)
        result = self.c.fetchone()
        self.log.debug("need worker for %s", result)
        return result

    def increase_downloads(self, image_path):
        self.log.debug("increase downloads of %s", image_path)
        sql = "UPDATE images_table SET downloads = downloads + 1 FROM images_download WHERE images_download.filename = ? and images_table.image_hash = images_download.image_hash"
        self.c.execute(sql, image_path)
        self.commit()

    def worker_register(self, name=datetime.datetime.now(), address=""):
        self.log.info("register worker %s %s", name, address)
        sql = """INSERT INTO worker (name, address, heartbeat)
            VALUES (?, ?, ?)
            RETURNING id;"""
        self.c.execute(sql, name, address, datetime.datetime.now())
        self.commit()
        return self.c.fetchone()[0]

    def worker_destroy(self, worker_id):
        self.log.info("destroy worker %s", worker_id)
        sql = """delete from worker where id = ?"""
        self.c.execute(sql, worker_id)
        self.commit()

    def worker_add_skill(self, worker_id, distro, release, target, subtarget, status):
        self.log.info("register worker skill %s %s", worker_id, status)
        sql = """INSERT INTO worker_skills
            select ?, subtargets.id, ? from subtargets
            WHERE distro = ? and release = ? and target LIKE ? and subtarget = ?;
            delete from imagebuilder_requests
            WHERE distro = ? and release = ? and target LIKE ? and subtarget = ?;"""
        self.c.execute(sql, worker_id, status, distro, release, target, subtarget, distro, release, target, subtarget)
        self.commit()

    def worker_heartbeat(self, worker_id):
        self.log.debug("heartbeat %s", worker_id)
        sql = "UPDATE worker SET heartbeat = ? WHERE id = ?"
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
        sql = """select coalesce(array_to_json(array_agg(row_to_json(distributions))), '[]') from distributions;"""
        return self.c.execute(sql).fetchone()[0]

    def get_supported_releases(self, distro):
        if distro == '': distro='%'
        sql = """select coalesce(array_to_json(array_agg(row_to_json(releases))), '[]') from releases where distro LIKE ?;"""
        return self.c.execute(sql, distro).fetchone()[0]

    def get_supported_models(self, model='', distro='', release=''):
        model_search = '%' + model + '%'
        if distro == '': distro = '%'
        if release == '': release = '%'
        sql = """select coalesce(array_to_json(array_agg(row_to_json(profiles))), '[]') from profiles where lower(model) LIKE lower(?) and distro LIKE ? and release LIKE ?;"""
        return self.c.execute(sql, model_search, distro, release).fetchone()[0]

    def get_subtargets_json(self, distro='%', release='%', target='%'):
        sql = """select coalesce(array_to_json(array_agg(row_to_json(subtargets))), '[]') from subtargets where distro like ? and release like ? and target like ?;"""
        self.c.execute(sql, distro, release, target)
        return self.c.fetchone()[0]

    def get_images_list(self):
        self.log.debug("get images list")
        sql = """select images.id, images.image_hash, images.distro, images.release, model, manifest_hash, network_profile, build_date, filename, images.filesize 
            from images join images_download on images.image_hash = images_download.image_hash join profiles on images.profile = profiles.profile
        order by id desc"""
        self.c.execute(sql)
        result = self.c.fetchall()
        return result

    def get_image_info(self, image_hash):
        self.log.debug("get image info %s", image_hash)
        sql = """select * from images"""
        self.c.execute(sql, image_hash)
        result = self.c.fetchone()
        return result

    def get_manifest_info(self, manifest_hash):
        self.log.debug("get manifest info %s", manifest_hash)
        sql = """select name, version from manifest_packages
            where manifest_hash = ?"""
        self.c.execute(sql, manifest_hash)
        result = self.c.fetchall()
        return result

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

    def packages_updates(self, distro, release, target, subtarget, packages):
        self.log.debug("packages updates")
        sql = """select name, version, installed_version from packages_available join (
                select key as installed_name, value as installed_version from json_each_text(?)
                ) as installed on installed.installed_name = packages_available.name
        where installed.installed_version != packages_available.version and
            distro = ? and release = ? and target = ? and subtarget = ?"""
        self.c.execute(sql, str(packages).replace("\'", "\""), distro, release, target, subtarget)
        result = self.c.fetchall()
        return result

    def flush_snapshots(self):
        self.log.debug("flush snapshots")
        sql = "delete from images where release = 'snapshot';"
        self.c.execute(sql)
        self.commit()

    def insert_transformation(self, distro, release, package, replacement, context):
        print("insert transformation {} {} {}".format(package, replacement, context))
        self.log.info("insert %s/%s ", distro, release)
        sql = "INSERT INTO transformations (distro, release, package, replacement, context) VALUES (?, ?, ?, ?, ?);"
        self.c.execute(sql, distro, release, package, replacement, context)
        self.commit()

    def transform_packages(self, distro, orig_release, dest_release, packages):
        self.log.debug("transform packages {} {} {} {}".format(distro, orig_release, dest_release, packages))
        sql = "select transform(?, ?, ?, ?)"
        self.c.execute(sql, distro, orig_release, dest_release, packages)
        return self.c.fetchall()
