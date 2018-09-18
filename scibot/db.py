from pathlib import Path
from datetime import datetime
from itertools import chain
from collections import namedtuple, defaultdict
import json
from h import models
from h.db import init
from h.util.uri import normalize as uri_normalize
from h.db.types import _get_hex_from_urlsafe, _get_urlsafe_from_hex, URLSafeUUID
from h.util.user import split_user
from h.models.document import update_document_metadata
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY
from hyputils.hypothesis import Memoizer
from scibot import config
from scibot.anno import quickload, quickuri, add_doc_all, validate, uri_normalization
from scibot.utils import makeSimpleLogger
from interlex.core import makeParamsValues  # FIXME probably need a common import ...
from IPython import embed


def getSession(dburi=config.dbUri(), echo=False):
    engine = create_engine(dburi, echo=echo)

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


class DbQueryFactory:
    """ parent class for creating converters for queries with uniform results """

    convert = tuple()
    query = ''

    def ___new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def __new__(cls, session):
        newcls = cls.bindSession(session)
        newcls.__new__ = cls.___new__
        return newcls

    @classmethod
    def bindSession(cls, session):
        # this approach seems better than overloading what __new__ does
        # and doing unexpected things in new
        classTypeInstance = type(cls.__name__.replace('Factory',''),
                                 (cls,),
                                 dict(session=session))
        return classTypeInstance

    def __init__(self, condition=''):
        self.condition = condition

    def execute(self, params=None, raw=False):
        if params is None:
            params = {}
        gen = self.session.execute(self.query + ' ' + self.condition, params)
        first = next(gen)
        if raw:
            yield first
            yield from gen
        else:
            Result = namedtuple(self.__class__.__name__ + 'Result', list(first.keys()))  # TODO check perf, seems ok?
            for result in chain((first,), gen):
                yield Result(*(c(v) if c else v for c, v in zip(self.convert, result)))

    @staticmethod
    def get_cols(model, no_id=True):
        cols = model.__table__.columns.keys()
        if no_id:
            cols.remove('id')

        return cols

    def _table_insert(self, table_things, table, cols):
        def do_defaults(thing, cols):
            for col in cols:
                value = getattr(thing, col)
                if value is None:
                    c = table.columns[col]
                    if c.default:  # TODO nullable check here?
                        value = c.default.arg

                yield value

        *templates, params = makeParamsValues(
            *([list(do_defaults(t, cols))]
                for t in table_things))

        col_expr = f'({", ".join(cols)})'
        sql = (f'INSERT INTO {table.name} {col_expr} VALUES ' +
                ', '.join(templates) +
                'RETURNING id')

        for thing, rp in zip(table_things, self.session.execute(sql, params)):
            thing.id = rp.id

    def insert_bulk(self, things, column_mapping=None, keep_id=False):
        # this works around the orm so be sure
        # to call session.expunge_all when done
        tables = set(t.__table__ for t in things)
        for table in tables:
            table_things = [t for t in things if t.__table__ == table]
            if column_mapping and table.name in column_mapping:
                cols = column_mapping[table.name]
            else:
                cols = self.get_cols(table_things[0].__class__)
            self._table_insert(table_things, table, cols)

    def __call__(self, params=None):
        return self.execute(params)

    def __iter__(self):
        """ works for cases without params """
        return self.execute()


class AnnoSyncFactory(Memoizer, DbQueryFactory):
    log = makeSimpleLogger('scibot.db.sync')
    convert = (lambda d: datetime.isoformat(d) + '+00:00',)  # FIXME hack
    query = 'SELECT updated FROM annotation'
    condition = 'WHERE groupid = :groupid ORDER BY updated DESC LIMIT 1'  # default condition

    def __init__(self, api_token=config.api_token, username=config.username,
                 group=config.group, memoization_file=None, condition=''):
        super().__init__(memoization_file, api_token=api_token, username=username, group=group)
        if condition:
            self.condition = condition

    def __call__(self):
        """ block upstream call which does undesirable things """
        raise NotImplemented

    def get_api_rows(self, search_after=None, stop_at=None):
        try:
            if self.group == '__world__':
                self.condition = 'WHERE groupid = :groupid AND userid = :userid '
                userid = f'acct:{self.username}@hypothes.is'  # FIXME other registration authorities
                last_updated = next(self.execute(params={'groupid':self.group,
                                                         'userid':userid})).updated
            else:
                last_updated = next(self.execute(params={'groupid':self.group})).updated
            self.log.debug(f'last updated at {last_updated} for {self.group}')
        except StopIteration:
            last_updated = None
            self.log.debug(f'no annotations in database for {self.group}')

        if self.memoization_file is None:
            rows = list(self.yield_from_api(search_after=last_updated, stop_at=stop_at))
        else:
            if last_updated:
                rows = [a._row for a in self.get_annos() if a.updated > last_updated]
            else:
                rows = [a._row for a in self.get_annos()]

        return rows

    def sync_annos(self, search_after=None, stop_at=None, api_rows=None, check=False):
        """ batch sync """

        if not api_rows:
            # TODO stream this using generators?
            api_rows = self.get_api_rows(search_after, stop_at)
            if not api_rows:
                self.log.info(f'all annotations are up to date')
                return

        anno_records = [quickload(r) for r in api_rows]
        self.log.debug(f'quickload complete for {len(api_rows)} api_rows')

        anno_id_to_doc_id = self.q_create_docs(api_rows)
        self.q_create_annos(anno_records, anno_id_to_doc_id)

        def do_check():
            self.log.debug('checking for consistency')
            annos = self.session.query(models.Annotation).all()
            #docs = self.session.query(models.Document).all()
            durs = self.session.query(models.DocumentURI).all()
            doc_uris = defaultdict(set)
            _ = [doc_uris[d.document_id].add(d.uri) for d in durs]
            doc_uris = dict(doc_uris)
            #dms = self.session.query(models.DocumentMeta).all()
            #doc_mismatch = [a for a in annos if anno_id_to_doc_id[a.id] != a.document.id]  # super slow due to orm fetches
            doc_mismatch = [a for a in annos if anno_id_to_doc_id[a.id] != a.document_id]
            assert not doc_mismatch, doc_mismatch
            # don't use the orm to do this, it is too slow even if you send the other queries above
            uri_mismatch = [(a.target_uri, doc_uris[a.document_id], a)
                            for a in annos
                            if a.target_uri not in doc_uris[a.document_id]]
            # NOTE hypothesis only allows 1 record per normalized uri, so we have to normalize here as well
            maybe_mismatch = set(frozenset(s) for u, s, a in uri_mismatch if not s.add(u))
            h_mismatch = set(s for s in maybe_mismatch if len(frozenset(uri_normalize(u) for u in s)) > 1)
            self.log.debug(f'h mismatch has {len(h_mismatch)} cases')
            # the above normalization is not sufficient for cases where there are two
            # hypothes.is normalized uris AND a scibot normalized uri as well
            super_mismatch = set(s for s in h_mismatch if len(frozenset(uri_normalization(u) for u in s)) > 1)
            assert not super_mismatch, super_mismatch

        if check:
            do_check()

            self.session.commit()
            self.log.debug('commit done')
        else:
            embed()

    def q_create_annos(self, anno_records, anno_id_to_doc_id):
        *values_templates, values, bindparams = makeParamsValues(*self.values_sets(anno_records, anno_id_to_doc_id),
                                                                 types=self.types(anno_records))
        rec_keys = self.get_rec_keys(anno_records)
        sql = text(f'INSERT INTO annotation ({", ".join(rec_keys)}) VALUES {", ".join(values_templates)}')
        sql = sql.bindparams(*bindparams)
        try:
            self.session.execute(sql, values)
            self.log.debug('anno execute done')
        except BaseException as e:
            self.log.error('YOU ARE IN ERROR SPACE')
            embed()

        self.session.flush()
        self.log.debug('anno flush done')

    def get_rec_keys(self, anno_records):
        def fix_reserved(k):
            if k == 'references':
                k = '"references"'

            return k

        return [fix_reserved(k) for k in anno_records[0].keys()] + ['document_id']

    def values_sets(self, anno_records, anno_id_to_doc_id):
        def type_fix(k, v):  # TODO is this faster or is type_fix?
            if isinstance(v, dict):
                return json.dumps(v)  # FIXME perf?
            elif isinstance(v, list):
                if any(isinstance(e, dict) for e in v):
                    return json.dumps(v)  # FIXME perf?
            return v

        def make_vs(d):
            id = d['id']
            document_id = anno_id_to_doc_id[id]
            return [type_fix(k, v) for k, v in d.items()] + [document_id],  # don't miss the , to make this a value set

        yield from (make_vs(d) for d in anno_records)
        self.log.debug('anno values sets done')

    def types(self, datas):
        def make_types(d):
            def inner(k):
                if k == 'id':
                    return URLSafeUUID
                elif k == 'references':
                    return ARRAY(URLSafeUUID)
                else:
                    return None
            return [inner(k) for k in d] + [None]  # note this is continuous there is no comma

        yield from (make_types(d) for d in datas)

    @staticmethod
    def uri_records(row):
        uri = row['uri']
        return uri, uri_normalization(uri), quickuri(row)

    def q_prepare_docs(self, rows):
        existing_unnormed = {r.uri:r.document_id
                             for r in self.session.execute('SELECT uri, document_id FROM document_uri')}
        _existing = defaultdict(set)
        _ = [_existing[uri_normalization(uri)].add(docid)
             for uri, docid in existing_unnormed.items()]
        assert not [_ for _ in _existing.values() if len(_) > 1]  # TODO proper handling for this case
        h_existing_unnormed = {uri_normalize(uri):docid
                               for uri, docid in existing_unnormed.items()}
        existing = {k:next(iter(v)) for k, v in _existing.items()}  # FIXME issues when things get big

        new_docs = {}  # FIXME this is completely opaque since it is not persisted anywhere
        for row in sorted(rows, key=lambda r: r['created']):
            id = row['id']
            uri, uri_normed, (created, updated, claims) = self.uri_records(row)
            try:
                docid = existing[uri_normed]
                doc = models.Document(id=docid)
                do_claims = False
            except KeyError:
                if uri_normed not in new_docs:
                    do_claims = True
                    doc = models.Document(created=created, updated=updated)
                    self.session.add(doc)  # TODO perf testing vs add_all
                    new_docs[uri_normed] = doc
                else:
                    do_claims = False
                    doc = new_docs[uri_normed]

            yield id, doc

            if uri_normalize(uri) not in h_existing_unnormed:
                # NOTE allowing only the normalized uri can cause confusion (i.e. see checks in sync_annos)
                h_existing_unnormed[uri_normalize(uri)] = doc
                # TODO do these get added automatically if their doc gets added but exists?
                doc_uri = models.DocumentURI(document=doc,
                                             claimant=uri,
                                             uri=uri,
                                             type='self-claim',
                                             created=created,
                                             updated=updated)
                yield None, doc_uri

            # because of how this schema is designed
            # the only way that this can be fast is
            # if we assume that all claims are identical
            # FIXME if there is a new claim type then we are toast though :/
            # the modelling here assumes that title etc can't change
            #print(id, uri, uri_normed, row['user'], row['uri'], row['created'])
            if do_claims:
                for claim in claims:
                    #print(id, uri, uri_normed, claim['claimant'], claim['type'], claim['value'])
                    dm = models.DocumentMeta(document=doc,
                                             created=created,
                                             updated=updated,
                                             **claim)
                    yield None, dm

    def q_create_docs(self, rows):
        ids_docs = list(self.q_prepare_docs(rows))
        docs = sorted(set(d for i, d in ids_docs if i), key=lambda d:d.created)
        uri_meta = list(d for i, d in ids_docs if not i)
        assert len(uri_meta) == len(set(uri_meta))

        # TODO skip the ones with document ids
        self.insert_bulk(docs, {'document':['created', 'updated']})

        for um in uri_meta:
            um.document_id = um.document.id
            um.document = None
            del um.document  # have to have this or doceument overrides document_id

        self.insert_bulk(uri_meta)
        self.session.expunge_all()  # preven attempts to add unpersisted
        self.session.flush()
        self.log.debug('finished inserting docs')
        anno_id_to_doc_id = {i:d.id for i, d in ids_docs}
        return anno_id_to_doc_id

    def h_prepare_document(self, row):
        datum = validate(row)
        document_dict = datum.pop('document')
        document_uri_dicts = document_dict['document_uri_dicts']
        document_meta_dicts = document_dict['document_meta_dicts']
        dd = row['id'], datum['target_uri'], row['created'], row['updated']
        return (*dd, document_uri_dicts, document_meta_dicts)

    def h_create_documents(self, rows):
        seen = {}
        for row in sorted(rows, key=lambda r:r['created']):
            id = row['id']
            p = self.h_prepare_document(row)
            id, target_uri, created, updated, document_uri_dicts, document_meta_dicts = p
            if target_uri in seen:
                yield id, seen[target_uri]
            else:
                document = update_document_metadata(  # TODO update normalization rules
                    self.session,
                    target_uri,
                    document_meta_dicts,
                    document_uri_dicts,
                    created=created,
                    updated=updated)
                seen[target_uri] = document
                yield id, document

    def sync_anno_stream(self, search_after=None, stop_at=None):
        """ streaming one anno at a time version of sync """
        for row in self.yield_from_api(search_after=last_updated, stop_at=stop_at):
            yield row, 'TODO'
            continue
            # TODO
            datum = validate(row)  # roughly 30x slower than quickload
            # the h code I'm calling assumes these are new annos
            datum['id'] = row['id']
            datum['created'] = row['created']
            datum['updated'] = row['updated']
            document_dict = datum.pop('document')
            document_uri_dicts = document_dict['document_uri_dicts']
            document_meta_dicts = document_dict['document_meta_dicts']
            a = [models.Annotation(**d,
                                   document_id=dbdocs[uri_normalize(d['target_uri'])].id)
                 for d in datas]  # slow
            self.log.debug('making annotations')
            self.session.add_all(a)
            self.log.debug('adding all annotations')


def uuid_to_urlsafe(uuid):
    return _get_urlsafe_from_hex(uuid.hex)


class AnnoQueryFactory(DbQueryFactory):
    convert = (
        uuid_to_urlsafe,
        lambda d: datetime.isoformat(d) + '+00:00',  # FIXME hack WARNING MAKE SURE ALL TIMESTAMPS THAT GO IN
        lambda d: datetime.isoformat(d) + '+00:00',  # FIXME hack ARE DERIVED FROM datetime.utcnow()
        None,
        lambda userid: split_user(userid)['username'],
        None,
        lambda lst: [uuid_to_urlsafe(uuid) for uuid in lst],
    )
    query = ('SELECT id, created, updated, target_uri, userid, tags, a.references '
             'FROM annotation AS a')


def bindSession(cls, session):
    return cls.bindSession(session)
