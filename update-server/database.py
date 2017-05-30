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


if __name__ == "__main__":
    db = Database()
    db.create_tables()
    db.update_package("zsh", "0.1", 100)
    db.update_package("bash", "0.1", 100)
    db.commit()
