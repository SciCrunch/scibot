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

    def sync_annos(self, search_after=None, stop_at=None):
        """ batch sync """
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
            self.log.debug(f'no annotations on record for {self.group}')

        if self.memoization_file is None:
            rows = list(self.yield_from_api(search_after=last_updated, stop_at=stop_at))
        else:
            if last_updated:
                rows = [a._row for a in self.get_annos() if a.updated > last_updated]
            else:
                rows = [a._row for a in self.get_annos()]

        if not rows:
            self.log.info(f'all annotations are up to date')
            return

        datas = [quickload(r) for r in rows]
        self.log.debug(f'quickload complete for {len(rows)} rows')

        id_doc = self.q_prepare_docs(rows)
        session.add_all((d for i, d in id_doc))
        self.log.debug('add all done')
        self.session.flush()  # get ids without commit
        self.log.debug('flush done')
        anno_id_to_doc_id = {i:d.id for i, d in id_doc}

        self.log.debug('values sets done')

        *values_templates, values, bindparams = makeParamsValues(*self.values_sets(datas, anno_id_to_doc_id),
                                                                 types=self.types(datas))
        sql = text(f'INSERT INTO annotation ({", ".join(keys)}) VALUES {", ".join(values_templates)}')
        sql = sql.bindparams(*bindparams)
        try:
            self.session.execute(sql, values)
        except BaseException as e:
            print('YOU ARE IN ERROR SPACE')
            embed()

        self.log.debug('execute done')

        self.session.flush()
        self.log.debug('flush done')

        embed()
        return
        self.session.commit()
        self.log.debug('commit done')

    def values_sets(self, datas, anno_to_doc):
        def fix_reserved(k):
            if k == 'references':
                k = '"references"'

            return k

        keys = [fix_reserved(k) for k in datas[0].keys()] + ['document_id']
        def type_fix(k, v):  # TODO is this faster or is type_fix?
            if isinstance(v, dict):
                return json.dumps(v)  # FIXME perf?
            elif isinstance(v, list):
                if any(isinstance(e, dict) for e in v):
                    return json.dumps(v)  # FIXME perf?
            return v

        def make_vs(d):
            id = d['id']
            document_id = anno_to_doc[id].id
            return [type_fix(k, v) for k, v in d.items()] + [document_id],  # don't miss the , to make this a value set

        yield from (make_vs(d) for d in datas)

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

    def uri_records(self, row):
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

        new_docs = {}
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
                h_existing_unnormed[uri_normalize(uri)] = doc
                # TODO do these get added automatically if their doc gets added but exists?
                doc_uri = models.DocumentURI(document=doc,
                                             claimant=uri,
                                             uri=uri,
                                             type='self-claim',
                                             created=created,
                                             updated=updated)

            # because of how this schema is designed
            # the only way that this can be fast is
            # if we assume that all claims are identical
            # FIXME if there is a new claim type then we are toast though :/
            # the modelling here assumes that title etc can't change
            #print(id, uri, uri_normed, row['user'], row['uri'], row['created'])
            if do_claims:
                for claim in claims:
                    #print(id, uri, uri_normed, claim['claimant'], claim['type'], claim['value'])
                    models.DocumentMeta(document=doc,
                                        created=created,
                                        updated=updated,
                                        **claim)


        return
        uris = {uri_normalize(j['uri']):quickuri(j)
                for j in sorted(rows,
                                # newest first so that the oldest value will overwrite
                                key=lambda j:j['created'],
                                reverse=True)}
        self.log.debug('uris done')

        if False:  # DOCS
            pass
        else:
            dcount = {r.uri:r.document_id  # FIXME can get nasty, but this is bulk
                    for r in self.session.execute('SELECT uri, document_id FROM document_uri')}
            if dcount:
                #self.session.bulk_insert_mappings(Document)
                embed()
                return
            else:
                dbdocs = {uri:add_doc_all(uri, created, updated, claims)  # FIXME default_dict, sort reverse too?
                        for uri, (created, updated, claims) in uris.items()}
                self.log.debug('dbdocs done')

                vals = list(dbdocs.values())
                self.session.add_all(vals)  # this is super fast locally and hangs effectively forever remotely :/ wat
                self.log.debug('add all done')
                self.session.flush()  # get ids without commit
                self.log.debug('flush done')

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
