#!/usr/bin/env python3.6
"""SciBot command line utilities

Usage:
    scibot db-init    [options] [<database>]
    scibot api-sync   [options] [<database>]
    scibot ws-sync    [options] [<database>]
    scibot debug      [options] [<database>]

Options:
    -h --help       show this
    -d --debug      enable echo and embed
"""

import os
from IPython import embed


def main():
    from docopt import docopt
    args = docopt(__doc__)
    database = args['<database>']
    if database is not None:
        os.environ.update({'SCIBOT_DATABASE': database})

    from scibot import config
    from scibot.db import getSession, init_scibot, AnnoSyncFactory

    if args['db-init']:
        # insurace, it is passed into init direclty as well
        #os.system(f'scibot-dbsetup {config.dbPort()} {database}')
        # the above should be done manually to prevent fat fingers
        init_scibot(database)

    elif args['api-sync']:
        session = getSession(echo=args['--debug'])
        AnnoSync = AnnoSyncFactory(session)
        cur_sync = AnnoSync(config.api_token, config.username,
                            config.group, config.memfile)
        cur_sync.sync_annos()
        pub_sync = AnnoSync(config.api_token, config.username,
                            config.group_staging, config.pmemfile)
        pub_sync.sync_annos()

    elif args['ws-sync']:
        'TODO'

    elif args['debug']:
        from time import time
        session = getSession(echo=args['--debug'])
        if True:
            dcount = {r.uri:r.document_id
                    for r in session.execute('SELECT uri, document_id FROM document_uri')}
            from h import models
            from hyputils.hypothesis import Memoizer
            from scibot.anno import disambiguate_uris
            from interlex.core import makeParamsValues
            mem = Memoizer(config.memfile, config.api_token, config.username, config.group)
            annos, last_updated = mem.get_annos_from_file()
            uris = set(a.uri for a in annos)
            dd = disambiguate_uris(uris)
            multi = [v for v in dd.values() if len(v) > 1]
            _rows = [a._row for a in annos]
            AnnoSync = AnnoSyncFactory(session)
            cur_sync = AnnoSync(config.api_token, config.username, config.group)

            rows = _rows
            # rows = [r for r in _rows if 'articles/4-42/' in r['uri']]
            # rows = [r for r in _rows if '10.1002/jnr.23615' in r['uri']]
            # rows = [r for r in _rows if 'ncomms8028' in r['uri']]  # TODO res chain these
            # rows = [r for r in _rows if '?term=Gene' in r['uri']]
            # rows = [r for r in _rows if 'index.php?' in r['uri']]
            # rows = [r for r in _rows if 'govhttp' in r['uri']]  # maximum wat

            if False:
                t0 = time()
                hdocs = list(cur_sync.h_create_documents(rows))
                t1 = time()
                session.flush()
                t2 = time()
                hload = t1 - t0
                hflush = t2 - t1
                print('h:', hload, hflush)
                # h: 174.50015807151794 0.0007216930389404297
                session.rollback()

            t3 = time()
            qdocs = list(cur_sync.q_prepare_docs(rows))  # now also duri and dm
            docs = sorted(set(d for i, d in qdocs if i), key=lambda d:d.created)
            other = list(d for i, d in qdocs if not i)
            assert len(other) == len(set(other))
            t4 = time()
            print('bulk saving')
            #session.add_all(docs)  # also monumentally slow
            # wow, don't use executemany kids, it is SLOW
            #session.bulk_insert_objects(list(d for i, d in qdocs))
            # and so is this ... wow these are :/
            #session.bulk_insert_mappings(models.Document,
                                         #[{'created':d.created,
                                           #'updated':d.updated}
                                          #for d in docs])


            def cols_less_id(model):
                cols = model.__table__.columns.keys()
                cols.remove('id')
                return cols

            def do_defaults(thing, cols, table):
                for col in cols:
                    value = getattr(thing, col)
                    if value is None:
                        c = table.columns[col]
                        if c.default:  # TODO nullable check here?
                            value = c.default.arg

                    yield value

            def insert_bulk(things, column_mapping):
                # this works around the orm so be sure
                # to call session.expunge_all when done
                tables = set(t.__table__ for t in things)
                for table in tables:
                    table_things = [t for t in things if t.__table__ == table]
                    cols = column_mapping[table.name]
                    *templates, params = makeParamsValues(
                        *([list(do_defaults(t, cols, table))]
                          for t in table_things))

                    col_expr = f'({", ".join(cols)})'
                    sql = (f'INSERT INTO {table.name} {col_expr} VALUES ' +
                           ', '.join(templates) +
                           'RETURNING id')

                    for thing, rp in zip(table_things, session.execute(sql, params)):
                        thing.id = rp.id


            # TODO skip the ones with document ids
            insert_bulk(docs, {'document':['created', 'updated']})

            for o in other:
                o.document_id = o.document.id
                o.document = None
                del o.document  # have to have this or doceument overrides document_id

            insert_bulk(other, {'document_uri':cols_less_id(models.DocumentURI),
                                'document_meta':cols_less_id(models.DocumentMeta)})

            #resp = list(session.execute('INSERT INTO document (created, updated) VALUES '
                                        #+ ' ,'.join(templates) + 'RETURNING id', params))
            # this doesn't completely work, the docs are not persisted according to sqla
            #for (i,), d in zip(resp, docs):
                #d.id = i

            session.expunge_all()


            #session.add_all(other)
            #session.flush()
            #session.add_all(other)
            #session.bulk_save_objects(list(d for i, d in qdocs if not i))
            print('flushing')
            session.flush()
            t5 = time()
            qload =  t4 - t3
            qflush = t5 - t4
            print('q:', qload, qflush)
            # q: 9.994797706604004 8.899968147277832
            # q: 10.092309474945068 10.236052513122559
            # q: 10.982917547225952 528.4648873806
            # method 'execute' of 'psycopg2.extensions.cursor' objects
            # is where the problem is
            embed()


if __name__ == '__main__':
    main()
