from sqlalchemy import create_engine
from urllib.parse import quote_plus

SRC_DB = {
    "driver": "mysql+pymysql",
    "host": "ai-db-rds.c83fh8gbkqpw.ap-south-1.rds.amazonaws.com",
    "port": 3306,
    "user": "ai-team",
    "password": "9zhEv_O592K14DD4@teRoW@05-:dn[NS",
    "database": "test_ai",
}

# SRC_DB = {
#     "driver": "mysql+pymysql",
#     "host": "bi-googlereadreplica.c83fh8gbkqpw.ap-south-1.rds.amazonaws.com",
#     "port": 3306,
#     "user": "adarsh",
#     "password": "XmbUd$5&haL&5^d*s#!2@",
#     "database": "sinterface",
# }

TGT_DB = {
    "driver": "mysql+pymysql",
    "host": "localhost",
    "port": 3306,
    "user": "harsh",
    "password": "Logieagle@123",
    "database": "staging",
}

def build_db_uri(cfg: dict) -> str:
    """
    Safely builds a SQLAlchemy DB URI from components.
    """
    password = quote_plus(cfg["password"])
    return (
        f'{cfg["driver"]}://'
        f'{cfg["user"]}:{password}@'
        f'{cfg["host"]}:{cfg["port"]}/'
        f'{cfg["database"]}'
    )

SOURCE_DB_URI = build_db_uri(SRC_DB)
TARGET_DB_URI = build_db_uri(TGT_DB)

source_engine = create_engine(
    SOURCE_DB_URI,
    pool_pre_ping=True
)

target_engine = create_engine(
    TARGET_DB_URI,
    pool_pre_ping=True
)
