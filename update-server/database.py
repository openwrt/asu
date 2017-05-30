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

    def createTables(self):
        logging.info("creating tables")
        with open('tables.sql') as t:
            self.c.execute(t.read())
        self.commit()
        logging.info("created tables")

    def addHash(self, hash, packages):
        sql = "INSERT INTO packageHashes (hash, packages) VALUES (?, ?)"
        self.c.execute(sql, (hash, " ".join(packages)))

    def updatePackage(self, name, version, size):
        logging.debug("insert %s %s %s", name, version, size)
        sql = "REPLACE INTO packages(name, version, size) VALUES (?, ?, ?)"
        self.c.execute(sql, name, version, size)

if __name__ == "__main__":
    db = Database()
    db.createTables()
    db.updatePackage("zsh", "0.1", 100)
    db.updatePackage("bash", "0.1", 100)
    db.commit()
