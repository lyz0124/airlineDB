import pymysql


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "air_reservation",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)
