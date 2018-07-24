#!/usr/bin/env python3.6
""" RRID export round 2

Usage:
    rridxp csv [options] [<filter>...]
    rridxp multi-id-report [options]

Examples:
    rridxp csv
    rridxp csv IMSR FILTER

Options:
    -h --help       show this
    -d --debug      drop into embed after jobs finish
"""

# Run these commands (with variables filled in) to retrieve the data
#  the first run may take ~30mins to synchronize all annotations
# export RRIDBOT_USERNAME=scibot
# export RRIDBOT_GROUP=${SCIBOT_CURATION_GROUP}
# export RRIDBOT_GROUP2=${SCIBOT_CURATION_GROUP}
# export RRIDBOT_GROUP_STAGING=__world__
# export RRIDBOT_API_TOKEN=${SCIBOT_API_TOKEN}
# export RRIDBOT_SYNC=$(head -c 100 /dev/urandom | tr -dc 'a-zA-Z0-9')

import csv
import json
from datetime import datetime
from pyontutils.utils import anyMembers
from IPython import embed

def UTCNOW():
    return datetime.isoformat(datetime.utcnow())

def deNone(*things):
    return tuple('' if thing is None else thing for thing in things)

def multiIssue(mp):
    return {d:{p:set(_.uri for _ in c.values())
               for p, c in r.items()
               if p is not None}
            for d, r in mp.items()
            if d is not None and
            len([k for k in r.keys() if k is not None]) > 1}

class Encode(json.JSONEncoder):
    def default(self, thing):
        if isinstance(thing, set):
            return list(thing)
        else:
            return super().default(thing)

def main():
    from docopt import docopt
    args = docopt(__doc__, version='rridxp 0.0.0')
    print(args)
    from scibot.release import get_annos, Curation, SamePMID, MultiplePMID, MultipleDOI, MPP, MPD
    annos = get_annos()
    [Curation(a, annos) for a in annos]
    def midr():
        mp = multiIssue(MultiplePMID(Curation))
        md = multiIssue(MultipleDOI(Curation))
        # filtering by url first removes any detectable instances of multiple dois/pmids
        #mpp = multiIssue(MPP(Curation))
        #mpd = multiIssue(MPD(Curation))
        with open('multiple-pmids.json', 'wt') as f:
            json.dump(mp, f, sort_keys=True, indent=4, cls=Encode)
        with open('multiple-dois.json', 'wt') as f:
            json.dump(md, f, sort_keys=True, indent=4, cls=Encode)

    if args['multi-id-report']:
        midr()

    elif args['csv']:
        substrings = args['<filter>']  # ['MGI', 'IMSR']
        if substrings:
            ssj = '-'.join(ss.lower() for ss in substrings) + '-'
        else:
            substrings = ['']
            ssj = 'all-'

        pmids2 = SamePMID(set(annotation
                              for paper in Curation._papers.values()
                              for rrid, annotations in paper.items()
                              if rrid is not None and anyMembers(rrid, *substrings)
                              for annotation in annotations))

        now = UTCNOW()
        rows = [['PMID', 'DOI', 'URI', 'shareLink', 'exact', 'rrid', 'public_tags']]
        rows += sorted(deNone(anno.pmid, anno.doi, anno.uri, anno.shareLink, anno.exact, anno.rrid, ','.join([t for t in anno.public_tags if 'RRID:' not in t]))
                       for pmid, papers in pmids2.items()
                       for rrids in papers.values()
                       for annos in rrids.values()
                       for anno in annos)
        with open(f'{ssj}rrids-{now}.csv', 'wt') as f:
            csv.writer(f, lineterminator='\n').writerows(rows)

        nomatch = [['PMID', 'DOI', 'URI', 'shareLink', 'exact', 'rrid', 'public_tags']]
        nomatch += sorted(deNone(anno.pmid, anno.doi, anno.uri, anno.shareLink, anno.exact, anno.rrid, ','.join([t for t in anno.public_tags if 'RRID:' not in t]))
                          for pmid, papers in pmids2.items()
                          for rrids in papers.values()
                          for annos in rrids.values()
                          for anno in annos
                          if anno.exact and anno.rrid and anno.exact not in anno.rrid)

        with open(f'{ssj}rrids-nomatch-{now}.csv', 'wt') as f:
            csv.writer(f, lineterminator='\n').writerows(nomatch)

    if args['--debug']:
        embed()

if __name__ == '__main__':
    main()
