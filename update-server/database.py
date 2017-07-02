from util import get_hash
import datetime
from config import Config
import pyodbc
import logging

class Database():
    def __init__(self):
        # python3 immport pyodbc; pyodbc.drivers()
        #self.cnxn = pyodbc.connect("DRIVER={SQLite3};SERVER=localhost;DATABASE=test.db;Trusted_connection=yes")
        self.log = logging.getLogger(__name__)
        self.config = Config()
        connection_string = "DRIVER={};SERVER=localhost;DATABASE={};UID={};PWD={};PORT={}".format(
                self.config.get("database_type"), self.config.get("database_name"), self.config.get("database_user"), 
                self.config.get("database_pass"), self.config.get("database_port"))
        self.cnxn = pyodbc.connect(connection_string)
        self.c = self.cnxn.cursor()
        self.log.debug("connected to databse")

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
        sql = "INSERT INTO releases VALUES (?, ?) ON CONFLICT DO NOTHING;"
        self.c.execute(sql, distro, release)
        self.commit()

    def insert_supported(self, distro, release, target, subtarget="%"):
        self.log.info("insert supported {} {} {} {}".format(distro, release, target, subtarget))
        sql = """UPDATE targets SET supported = true
            WHERE 
                distro=? AND 
                release=? AND 
                target=? AND 
                subtarget LIKE ?"""
        self.c.execute(sql, distro, release, target, subtarget)
        self.commit()

    def get_releases(self, distro=None):
        if not distro:
            return self.c.execute("select * from releases").fetchall()
        else:
            releases = self.c.execute("select release from releases WHERE distro=?", (distro, )).fetchall()
            respond = []
            for release in releases:
                respond.append(release[0])
            return respond

    def insert_hash(self, hash, packages):
        sql = """INSERT INTO packages_hashes
            VALUES (?, ?)
            ON CONFLICT DO NOTHING;"""
        self.c.execute(sql, (hash, " ".join(packages)))
        self.commit()

    def insert_profiles(self, distro, release, target, subtarget, profiles_data):
        self.log.debug("insert_profiels %s/%s/%s/%s", distro, release, target, subtarget)
        default_packages, profiles = profiles_data
        sql = """INSERT INTO profiles 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING;"""
        for profile in profiles:
            self.c.execute(sql, distro, release, target, subtarget, *profile)
        self.c.execute("INSERT INTO default_packages VALUES (?, ?, ?, ?, ?) on conflict do nothing;", distro, release, target, subtarget, default_packages)
        self.commit()

    def check_profile(self, distro, release, target, subtarget, profile):
        self.log.debug("check_profile %s/%s/%s/%s/s", distro, release, target, subtarget, profile)
        self.c.execute("""SELECT EXISTS(
            SELECT 1 FROM profiles
            WHERE 
                distro=? AND 
                release=? AND 
                target=? AND 
                subtarget = ? AND 
                (name = ? OR board = ?)
            LIMIT 1);""",
            distro, release, target, subtarget, profile, profile)
        if self.c.fetchone()[0]:
            return True
        return False

    def get_default_packages(self, distro, release, target, subtarget):
        self.log.debug("get_default_packages for %s/%s", target, subtarget)
        self.c.execute("""SELECT packages
            FROM default_packages
            WHERE 
                distro=? AND 
                release=? AND 
                target=? AND 
                subtarget=?;""", 
            distro, release, target, subtarget)
        response = self.c.fetchone()
        if response:
            return response[0].split(" ")
        return response

    def insert_packages(self, distro, release, target, subtarget, packages):
        self.log.info("insert packages of %s/%s ", target, subtarget)
        sql = """INSERT INTO packages
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING;"""
        for package in packages:
            # (name, version)
            self.c.execute(sql, distro, release, target, subtarget, *package)
        self.commit()

    def get_available_packages(self, distro, release, target, subtarget):
        self.log.debug("get_available_packages for %s/%s/%s/%s", distro, release, target, subtarget)
        self.c.execute("""SELECT name, version
            FROM packages 
            WHERE 
                distro=? AND 
                release=? AND 
                target=? AND 
                subtarget=?;""", 
            distro, release, target, subtarget)
        response = {}
        for name, version in self.c.fetchall():
            response[name] = version 
        return response
    
    def insert_target(self, distro, release, target, subtargets):
        self.log.info("insert %s/%s ", target, " ".join(subtargets))
        sql = "INSERT INTO targets VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING;"
        for subtarget in subtargets:
            self.c.execute(sql, distro, release, target, subtarget)

        self.commit()

    def get_targets(self, distro, release, target="%", subtarget="%"):
        self.log.debug("get_targets {} {} {} {}".format(distro, release, target, subtarget))
        return self.c.execute("""SELECT target, subtarget, supported FROM targets
            WHERE 
                distro = ? AND 
                release = ? AND 
                target LIKE ? AND 
                subtarget LIKE ?;""", 
            distro, release, target, subtarget).fetchall()

    def get_image_status(self, image):
        sql = """select id, status, checksum, filesize from images
            where image_hash = ?"""
        self.c.execute(sql, (get_hash(" ".join(image.as_array()), 12)))
        if self.c.description:
            return self.c.fetchone()
        else:
            return None

    def add_build_job(self, image):
        sql = """INSERT INTO images
            (image_hash, distro, release, target, subtarget, profile, package_hash, network_profile)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?) 
            ON CONFLICT DO NOTHING
            RETURNING id"""
        image_array = image.as_array()
        self.c.execute(sql, (get_hash(" ".join(image_array), 12), *image_array, ))
        if self.c.description:
            self.commit()
            return self.c.fetchone()[0]
        else:
            return None

    def get_last_build_id(self):
        sql = """SELECT MIN(id) FROM images;"""
        self.c.execute(sql)
        if self.c.description:
            self.commit()
            return self.c.fetchone()[0]
        else:
            return None

    def get_build_job(self):
        sql = """UPDATE images
            SET status = 'building'
            FROM packages_hashes
            WHERE images.package_hash = packages_hashes.hash AND status = 'requested' AND id = (
                SELECT MIN(id)
                FROM images
                WHERE status = 'requested'
                )
            RETURNING id, image_hash, distro, release, target, subtarget, profile, packages_hashes.packages, network_profile;"""
        self.c.execute(sql)
        if self.c.description:
            self.commit()
            return self.c.fetchone()
        else:
            return None
    
    def reset_build_job(self, image):
        image_request_hash = get_hash(" ".join(image), 12)
        sql = """UPDATE images
            SET status = 'requested'
            WHERE image_hash = ?;"""
        self.c.execute(sql, (image_request_hash, ))
        self.commit()

    def set_build_job_fail(self, image_request_hash):
        sql = """UPDATE images
            SET status = 'failed'
            WHERE image_hash = ?;"""
        self.c.execute(sql, (image_request_hash, ))
        self.commit()

    def done_build_job(self, image_request_hash, checksum, filesize):
        sql = """UPDATE images SET 
            status = 'created',
            checksum = ?,
            filesize = ?,
            build_date = ?
            WHERE image_hash = ?;"""
        self.c.execute(sql, checksum, filesize, datetime.datetime.now(), image_request_hash)
        self.commit()

    def get_imagebuilder_status(self, distro, release, target, subtarget):
        sql = """select status from imagebuilder
            WHERE 
                distro=? AND 
                release=? AND 
                target=? AND 
                subtarget=?;"""
        self.c.execute(sql, distro, release, target, subtarget)
        if self.c.rowcount > 0:
            return self.c.fetchone()[0]
        else:
            sql = """INSERT INTO imagebuilder (distro, release, target, subtarget) 
                VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING;"""
            self.c.execute(sql, (distro, release, target, subtarget))
            self.commit()
            return 'requested'
    
    def set_imagebuilder_status(self, distro, release, target, subtarget, status):
        sql = """UPDATE imagebuilder SET status = ?
            WHERE 
                distro=? AND 
                release=? AND 
                target=? AND 
                subtarget=?"""
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
        
if __name__ == "__main__":
    db = Database()
    db.create_tables()
