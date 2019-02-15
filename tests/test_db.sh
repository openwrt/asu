#!/bin/sh

# run this as logged in postgres user

psql asu < reset.sql
psql asu < ../asu/utils/tables.sql
psql asu < inserts.sql
psql asu < functions.sql

