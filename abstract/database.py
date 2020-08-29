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
            self.con = pymysql.Connect(config.hostname, config.username, config.password, config.path.lstrip('/'),
                                       autocommit=True)
        else:
            with open('mysql.yaml') as c:
                config = yaml.safe_load(c)
            self.con = pymysql.Connect(config['host'], config['username'], config['password'], config['db'],
                                       autocommit=True)

        atexit.register(lambda: self.con.close())
