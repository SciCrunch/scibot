#!/usr/bin/env python3.6
import csv
from collections import namedtuple, Counter
from scibot.release import Curation, PublicAnno, get_annos, get_pannos
from scibot.utils import uri_normalization
from IPython import embed


def dbUri(user='nif_eelg_secure', host='nif-mysql.crbs.ucsd.edu', port=3306, database='nif_eelg'):
    DB_URI = 'mysql+pymysql://{user}:{password}@{host}:{port}/{db}'  # FIXME db => pyontutils refactor
    if socket.gethostname() in config.dev_remote_hosts:
        db_cfg_kwargs = mysql_conn_helper('localhost', database, user, 33060)  # see .ssh/config
    else:
        db_cfg_kwargs = mysql_conn_helper(host, database, user, port)

    return DB_URI.format(**db_cfg_kwargs)


class RRIDData:
    def __init__(self, session):
        self.session = session

    def james_rrids(self):
        sql = '''SELECT m.uri, v.pmid, v.rrid, m.annotation_id,
        m.hypothesis_user, v.journal, v.title, v.year
        FROM rrid_mentions_view2 AS v JOIN rrid_mentions AS m ON v.rrid_mention_id = m.id
        WHERE source = 'Hypothesis' '''
        yield from self.session.execute(sql)

    def combine(self, rrid_recs=None):
        if rrid_recs is None:
            rrid_recs = self.james_rrids()

        header =  ('release', 'issue', 'urin', 'uri',
                   'pmid', 'cpmid', 'doi', 'rrid', 'crrid',
                   'rlink', 'alink', 'plink',
                   'user', 'journal', 'title', 'year')#, 'ptext')
        rr = namedtuple('reprow', header)
        yield rr(*header)
        pa_done = set()
        for row in rrid_recs:
            #print(row)
            c = Curation.byId(row.annotation_id)
            errorl = []
            if c is None:

                yield rr(None, 'BAD-ANNOTATION-ID', None, row.uri,
                         row.pmid, None, None, row.rrid, None,
                         None, row.annotation_id, None,
                         row.hypothesis_user, row.journal, row.title, row.year)#, None)
                continue

            else:
                if row.uri != c.uri:
                    errorl.append('URI-mismatch')
                if row.pmid != c.pmid:
                    errorl.append('PMID-mismatch')
                if row.rrid != c.rrid:
                    errorl.append('RRID-mismatch')

            issue = ' '.join(errorl)
            pa = c._public_anno if c else None
            pasl = pa.shareLink if pa is not None else None
            pat = pa.text if pa is not None else None
            if pa is not None:
                pa_done.add(pa.id)
            yield rr(c.isReleaseNode, issue, c.uri_normalized, row.uri,
                     row.pmid, c.pmid, c.doi, row.rrid, c.rrid,
                     c.rridLink, c.shareLink, pasl,
                     row.hypothesis_user, row.journal, row.title, row.year)#, pat)

        rissue = 'RELEASED-BUT-NOT-IN-TABLE'
        for pa in PublicAnno:
            if pa.id not in pa_done:
                cs = list(pa.curation_annos)
                if not cs:
                    irn = None
                    issue = 'DELETE-THIS'
                    cpmid = None
                    cdoi = None
                    cshareLink = None
                    curators = ''  # FIXME look this up?
                else:
                    issue = rissue
                    irn = all(c.isReleaseNode if c is not None else c for c in cs)
                    if not irn:
                        if None in cs:
                            issue = '!?-WHAT-HAVE-YOU-DONE!?-WHERE-IS-MY-CURATION-ANNO!? ' + issue
                            cs = [c for c in cs if c is not None]

                    if not cs:
                        irn = None
                        issue = 'DELETE-THIS ' + issue
                        cpmid = None
                        cdoi = None
                        cshareLink = None
                    else:
                        cdoi = cs[0].doi  # NOTE this MASSIVE CHANGES semantics of the rrid column
                        if cdoi != pa.doi:
                            issue = 'DOI-mismatch ' + issue

                        cpmid = cs[0].pmid  # NOTE this changes semantics of the pmid column
                        if cpmid != pa.pmid:
                            issue = 'PMID-mismatch ' + issue


                        cshareLink = cs[0].shareLink

                        curators = ' '.join([c for ca in cs for c in ca.curators])

                issue = 'z ' + issue  # ordering
                yield rr(irn, issue, pa.uri_normalized, pa.uri,
                         pa.pmid, cpmid, cdoi, pa.doi, pa.rrid,
                         pa.rridLink, cshareLink, pa.shareLink,
                         curators, None, None, None)#, pa.text)


def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm.session import sessionmaker
    engine = create_engine(dbUri(), echo=True)
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()

    annos = get_annos()
    Curation._annos_list = annos
    pannos = get_pannos()
    PublicAnno._annos_list = pannos

    for helper in (Curation, PublicAnno):
        [helper(a, helper._annos_list) for a in helper._annos_list]

    def key(r):
        i = r.issue if r.issue else ''
        p = r.pmid if r.pmid else ''
        u = r.urin if r.urin else ''
        c = r.crrid if r.crrid else ''
        return i, p, u, c

    rd = RRIDData(session)
    rrid_recs = [r for r in rd.james_rrids() if r.uri]

    rd = RRIDData(session)
    gen = rd.combine(rrid_recs)
    report = [next(gen)] + sorted(gen, key=key)
    bads = [r for r in report if r.issue]
    noanno = [r for r in bads if not r.urin]
    noalink = [r for r in noanno if not r.alink]
    noannoalink = [r for r in noanno if r.alink]

    badwanno = [r for r in bads if r.urin]

    irep = {}
    for r in report:
        if r.alink not in irep:
            irep[r.alink] = set()

        irep[r.alink].add(r)

    duplicates = {k:v for k, v in irep.items() if len(v) > 1}

    with open('scibot-rrid-bads.csv', 'wt') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerows(bads)

    with open('scibot-rrid-all.csv', 'wt') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerows(report)

    embed()


if __name__ == '__main__':
    main()
