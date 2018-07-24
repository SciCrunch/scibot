#!/usr/bin/env python3.6

# Run these commands (with variables filled in) to retrieve the data
#  the first run may take ~30mins to synchronize all annotations
# export RRIDBOT_USERNAME=scibot
# export RRIDBOT_GROUP=${SCIBOT_CURATION_GROUP}
# export RRIDBOT_GROUP2=${SCIBOT_CURATION_GROUP}
# export RRIDBOT_GROUP_STAGING=__world__
# export RRIDBOT_API_TOKEN=${SCIBOT_API_TOKEN}
# export RRIDBOT_SYNC=$(head -c 100 /dev/urandom | tr -dc 'a-zA-Z0-9')

import csv
from scibot.release import get_annos, Curation, SamePMID
def deNone(*things):
    return tuple('' if thing is None else thing for thing in things)

def main():
    annos = get_annos()
    [Curation(a, annos) for a in annos]
    pmids2 = SamePMID(set(annotation
                          for paper in Curation._papers.values()
                          for rrid, annotations in paper.items()
                          if rrid is not None and ('MGI' in rrid or 'IMSR' in rrid)
                          for annotation in annotations))

    rows = [['PMID', 'DOI', 'URI', 'shareLink', 'exact', 'rrid', 'public_tags']]
    rows += sorted(deNone(anno.pmid, anno.doi, anno.uri, anno.shareLink, anno.exact, anno.rrid, ','.join([t for t in anno.public_tags if 'RRID:' not in t]))
                   for pmid, papers in pmids2.items()
                   for rrids in papers.values()
                   for annos in rrids.values()
                   for anno in annos)
    with open('mgi-imsr-rrids.csv', 'wt') as f:
        csv.writer(f, lineterminator='\n').writerows(rows)

    nomatch = [['PMID', 'DOI', 'URI', 'shareLink', 'exact', 'rrid', 'public_tags']]
    nomatch += sorted(deNone(anno.pmid, anno.doi, anno.uri, anno.shareLink, anno.exact, anno.rrid, ','.join([t for t in anno.public_tags if 'RRID:' not in t]))
                      for pmid, papers in pmids2.items()
                      for rrids in papers.values()
                      for annos in rrids.values()
                      for anno in annos
                      if anno.exact and anno.rrid and anno.exact not in anno.rrid)

    with open('mgi-imsr-rrids-nomatch.csv', 'wt') as f:
        csv.writer(f, lineterminator='\n').writerows(nomatch)

if __name__ == '__main__':
    main()
