from pathlib import Path
from h.db import init
from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker
from scibot import config


def getSession(dburi=config.dbUri()):
    engine = create_engine(dburi)

    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    return session


def init_scibot(database):
    dburi = config.dbUri(user='scibot-admin', database=database)
    #dburi = dbUri('postgres')
    engine = create_engine(dburi)
    init(engine, should_create=True, authority='scicrunch')

    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    file = Path(__file__).parent / '../sql/permissions.sql'
    with open(file.as_posix(), 'rt') as f:
        sql = f.read()
    #args = dict(database=database)
    # FIXME XXX evil replace
    sql_icky = sql.replace(':database', f'"{database}"')
    session.execute(sql_icky)
    session.commit()


