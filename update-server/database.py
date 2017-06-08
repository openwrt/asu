import sqlite3
import pyodbc
import logging

logging.basicConfig(level=logging.DEBUG)

class Database():
    def __init__(self):
        # python3 immport pyodbc; pyodbc.drivers()
        #self.cnxn = pyodbc.connect("DRIVER={SQLite3};SERVER=localhost;DATABASE=test.db;Trusted_connection=yes")
        self.cnxn = pyodbc.connect("DRIVER={PostgreSQL Unicode};SERVER=localhost;DATABASE=attended-sysupgrade;UID=postgres;PWD=password;PORT=5432")
        self.c = self.cnxn.cursor()
        logging.debug("connected to databse")

    def commit(self):
        self.cnxn.commit()
        logging.debug("database commit")

    def create_tables(self):
        logging.info("creating tables")
        with open('tables.sql') as t:
            self.c.execute(t.read())
        self.commit()
        logging.info("created tables")

    def insert_hash(self, hash, packages):
        sql = """INSERT INTO packages_hashes (hash, packages) 
            VALUES (?, ?)
            ON CONFLICT DO NOTHING;"""
        self.c.execute(sql, (hash, " ".join(packages)))
        self.commit()

    def update_package(self, name, version, size):
        logging.debug("insert %s %s %s", name, version, size)
        sql = "INSERT INTO packages(name, version, size) VALUES (?, ?, ?)"
        self.c.execute(sql, name, version, size)

    def insert_profiles(self, target, subtarget, profiles_data):
        logging.debug("insert_profiels %s/%s", target, subtarget)
        default_packages, profiles = profiles_data

        logging.info("insert profiles of %s/%s ", target, subtarget)
        sql = "INSERT INTO profiles (target, subtarget, name, board, packages) VALUES (?, ?, ?, ?, ?)"
        for profile in profiles:
            self.c.execute(sql, target, subtarget, *profile)

        self.c.execute("INSERT INTO default_packages (target, subtarget, packages) VALUES (?, ?, ?)", target, subtarget, default_packages)
        self.commit()

    def get_default_packages(self, target, subtarget):
        logging.debug("get_default_pkgs for %s/%s", target, subtarget)
        self.c.execute(""" SELECT packages FROM default_packages
            WHERE target=? AND subtarget=?;""", target, subtarget)
        response = self.c.fetchone()
        logging.debug("get_default_packages response: %s", response)
        if response:
            return response[0].split(" ")
        return response

    def insert_packages(self, target, subtarget, packages):
        logging.info("insert packages of %s/%s ", target, subtarget)
        sql = "INSERT INTO packages (name, version, size, target, subtarget) VALUES (?, ?, ?, ?, ?)"
        for package in packages:
            self.c.execute(sql, *package, target, subtarget)

        self.commit()
    
    def insert_target(self, target, subtargets):
        logging.info("insert %s/%s ", target, " ".join(subtargets))
        sql = "INSERT INTO targets (target, subtarget) VALUES (?, ?)"
        for subtarget in subtargets:
            self.c.execute(sql, target, subtarget)

        self.commit()

    def check_target(self, target, subtarget):
        logging.debug("check for %s/%s", target, subtarget)
        self.c.execute("""SELECT EXISTS(
            SELECT 1 FROM targets 
            WHERE target=? AND subtarget = ? 
            LIMIT 1);""",
            target, subtarget)
        if self.c.fetchone()[0]:
            return True
        else:
            logging.info("check fail for %s/%s", target, subtarget)
            return False

    # just a dummy for now
    def check_packages(self, target, subtarget, packages):
        logging.debug("check packages %s", packages)
        return packages
        




if __name__ == "__main__":
    db = Database()
    db.create_tables()
    db.check_target("ar71xx", "generic")
    db.check_target("ar71xx", "special")
