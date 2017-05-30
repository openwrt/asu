import sqlite3
import pyodbc
import logging

logging.basicConfig(level=logging.DEBUG)

class Database():
    def __init__(self):
        self.cnxn = pyodbc.connect("DRIVER={SQLite3};SERVER=localhost;DATABASE=test.db;Trusted_connection=yes")
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

    def add_hash(self, hash, packages):
        sql = "INSERT INTO packageHashes (hash, packages) VALUES (?, ?)"
        self.c.execute(sql, (hash, " ".join(packages)))

    def update_package(self, name, version, size):
        logging.debug("insert %s %s %s", name, version, size)
        sql = "REPLACE INTO packages(name, version, size) VALUES (?, ?, ?)"
        self.c.execute(sql, name, version, size)

    def insert_profiles(self, target, subtarget, profiles_data):
        default_packages, profiles = profiles_data

        logging.info("insert profiles of %s/%s ", target, subtarget)
        sql = "REPLACE INTO profiles (target, subtarget, name, board, packages) VALUES (?, ?, ?, ?, ?)"
        for profile in profiles:
            self.c.execute(sql, target, subtarget, *profile)

        self.c.execute("REPLACE INTO default_packages (target, subtarget, packages) VALUES (?, ?, ?)", target, subtarget, default_packages)
        self.commit()

    def insert_packages(self, target, subtarget, packages):
        logging.info("insert packages of %s/%s ", target, subtarget)
        sql = "REPLACE INTO packages (name, version, size, target, subtarget) VALUES (?, ?, ?, ?, ?)"
        for package in packages:
            self.c.execute(sql, *package, target, subtarget)

        self.commit()
    
    def insert_target(self, target, subtargets):
        logging.info("insert %s/%s ", target, " ".join(subtargets))
        sql = "REPLACE INTO targets (target, subtarget) VALUES (?, ?)"
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
