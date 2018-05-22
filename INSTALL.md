# Installation Notes

## Prerequites 

- Debian/Ubuntu
    - anything Unixlike should work but commands may differ
- Python3 + venv Module  
- PostgreSQL 
- GnuPG 
- Working Compiler 


    # apt install python3-dev python3-venv build-essential cmake git postgresql-10 
    
    
### 1. Clone Repository 

    $ git clone https://github.com/weimarnetz/attendedsysupgrade-server.git 
    $ git checkout -b dev 
    
### 2. Setup virtualenv 

    $ cd attendedsysupgrade-server
    $ . venv/bin/activate
    // update pip  
    $ pip -U pip 
    // install requirements
    $ pip -r requirements.txt 
    
### 3. Setup Database 

    $ sudo -u postgres -i 
    $ psql -U postgres
    CREATE ROLE sysupgrade LOGIN password 'secret';
    CREATE DATABASE attended-sysupgrade ENCODING 'UTF8' OWNER sysupgrade;
    

- Copy   utils/config.yml.default to the  attendedsysupgrade-server  folder and add the credentials for the database
 
- Import the SQL in  utils/tables.sql:
 

    $ psql -U sysupgrade --password -h localhost -d attended-sysupgrade < utils/tables.sql 

- Start the Server:
 

    $ ./cli.py -ia 
        