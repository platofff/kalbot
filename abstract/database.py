import atexit
from os import environ
from urllib.parse import urlparse

import pymysql
import yaml


class Database:
    con: pymysql.connections.Connection

    def __init__(self):
        if 'DATABASE_URL' in environ:
            config = urlparse(environ['DATABASE_URL'])
            self.con = pymysql.Connect(host=config.hostname, user=config.username, password=config.password,
                                       database=config.path.lstrip('/'), autocommit=True)
        else:
            with open('mysql.yaml') as c:
                config = yaml.safe_load(c)
            self.con = pymysql.Connect(host=config['host'], user=config['username'], password=config['password'],
                                       database=config['db'], autocommit=True)

        atexit.register(lambda: self.con.close())
