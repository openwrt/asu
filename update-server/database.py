from util import get_hash
import pyodbc
import logging

class Database():
    def __init__(self):
        # python3 immport pyodbc; pyodbc.drivers()
        #self.cnxn = pyodbc.connect("DRIVER={SQLite3};SERVER=localhost;DATABASE=test.db;Trusted_connection=yes")
        self.log = logging.getLogger(__name__)
        self.cnxn = pyodbc.connect("DRIVER={PostgreSQL Unicode};SERVER=localhost;DATABASE=attended-sysupgrade;UID=postgres;PWD=password;PORT=5432")
        self.c = self.cnxn.cursor()
        self.log.debug("connected to databse")

    def commit(self):
        self.cnxn.commit()
        self.log.debug("database commit")

    def create_tables(self):
        self.log.info("creating tables")
        with open('tables.sql') as t:
            self.c.execute(t.read())
        self.commit()
        self.log.info("created tables")

    def insert_hash(self, hash, packages):
        sql = """INSERT INTO packages_hashes (hash, packages) 
            VALUES (?, ?)
            ON CONFLICT DO NOTHING;"""
        self.c.execute(sql, (hash, " ".join(packages)))
        self.commit()

    def update_package(self, name, version, size):
        self.log.debug("insert %s %s %s", name, version, size)
        sql = "INSERT INTO packages(name, version, size) VALUES (?, ?, ?)"
        self.c.execute(sql, name, version, size)

    def insert_profiles(self, target, subtarget, profiles_data):
        self.log.debug("insert_profiels %s/%s", target, subtarget)
        default_packages, profiles = profiles_data

        sql = "INSERT INTO profiles (target, subtarget, name, board, packages) VALUES (?, ?, ?, ?, ?)"
        for profile in profiles:
            self.c.execute(sql, target, subtarget, *profile)

        self.c.execute("INSERT INTO default_packages (target, subtarget, packages) VALUES (?, ?, ?)", target, subtarget, default_packages)
        self.commit()

    def check_profile(self, target, subtarget, profile):
        self.log.debug("check_profile  %s/%s/s", target, subtarget, profile)
        self.c.execute("""SELECT EXISTS(
            SELECT 1 FROM profiles
            WHERE target=? AND subtarget = ? AND (name = ? OR board = ?)
            LIMIT 1);""",
            target, subtarget, profile, profile)
        if self.c.fetchone()[0]:
            return True
        return False

    def get_default_packages(self, target, subtarget):
        self.log.debug("get_default_packages for %s/%s", target, subtarget)
        self.c.execute(""" SELECT packages FROM default_packages
            WHERE target=? AND subtarget=?;""", target, subtarget)
        response = self.c.fetchone()
        self.log.debug("get_default_packages response: %s", response)
        if response:
            return response[0].split(" ")
        return response

    def get_available_packages(self, target, subtarget):
        self.log.debug("get_available_packages for %s/%s", target, subtarget)
        self.c.execute(""" SELECT name, version FROM packages 
            WHERE target=? AND subtarget=?;""", target, subtarget)
        response = {}
        for name, version in self.c.fetchall():
            response[name] = version 
        return response

    def insert_packages(self, target, subtarget, packages):
        self.log.info("insert packages of %s/%s ", target, subtarget)
        sql = "INSERT INTO packages (name, version, target, subtarget) VALUES (?, ?, ?, ?)"
        for package in packages:
            self.c.execute(sql, *package, target, subtarget)

        self.commit()
    
    def insert_target(self, target, subtargets):
        self.log.info("insert %s/%s ", target, " ".join(subtargets))
        sql = "INSERT INTO targets (target, subtarget) VALUES (?, ?)"
        for subtarget in subtargets:
            self.c.execute(sql, target, subtarget)

        self.commit()

    def get_targets(self):
        return self.c.execute("select target, subtarget from targets").fetchall()

    def check_target(self, target, subtarget):
        self.log.debug("check for %s/%s", target, subtarget)
        self.c.execute("""SELECT EXISTS(
            SELECT 1 FROM targets 
            WHERE target=? AND subtarget = ? 
            LIMIT 1);""",
            target, subtarget)
        if self.c.fetchone()[0] != "0":
            return True
        else:
            self.log.info("check fail for %s/%s", target, subtarget)
            return False

    def add_build_job(self, image):
        sql = """INSERT INTO build_queue
            (image_hash, distro, version, target, subtarget, profile, packages, network_profile)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?) 
            ON CONFLICT (image_hash) DO UPDATE
            SET id = build_queue.id
            RETURNING id, status;"""
        image_array = image.as_array()
        self.c.execute(sql, (get_hash(" ".join(image_array), 12), *image_array))
        self.commit()
        if self.c.description:
            return self.c.fetchone()
        else:
            return None

    def get_build_job(self):
        sql = """UPDATE build_queue
            SET status = 1
            WHERE status = 0 AND id = (
                SELECT MIN(id)
                FROM build_queue
                WHERE status = 0
                )
            RETURNING * ;"""
       # sql = """SELECT * 
       #     FROM build_queue
       #     WHERE id = (
       #         SELECT MIN(id) 
       #         FROM build_queue
       #     );"""
        self.c.execute(sql)
        if self.c.description:
            self.commit()
            return self.c.fetchone()
        else:
            return None

    def set_build_job_fail(self, image_request_hash):
        sql = """UPDATE build_queue
            WHERE image_hash = ?
            SET status = 2;"""
        self.c.execute(sql, (image_request_hash, ))
        self.commit()

    def del_build_job(self, image_request_hash):
        sql = """DELETE FROM build_queue
            WHERE image_hash = ?;"""
        self.c.execute(sql, (image_request_hash, ))
        self.commit()
        
if __name__ == "__main__":
    db = Database()
    db.create_tables()
    db.check_target("ar71xx", "generic")
    db.check_target("ar71xx", "special")
