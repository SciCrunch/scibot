#!/usr/bin/env python3.6
"""Merge new raw json annos into a memoized store
DO NOT RUN ON A LIVE STORE

Usage:
    anno-merge <file>

"""
import json
from collections import Counter
from hyputils.hypothesis import HypothesisAnnotation, Memoizer
from scibot.core import memfile, api_token, username, group
from docopt import docopt
from IPython import embed

get_annos = Memoizer(memfile, api_token, username, group, 200000)

def main():
    args = docopt(__doc__)
    some_file = args['<file>']  # TODO find these automatically
    with open(some_file, 'rt') as f:
        new_annos_json = json.load(f)
    annos = get_annos()
    new_annos = [HypothesisAnnotation(janno) for janno in new_annos_json]
    if annos[0].group != new_annos[0].group:
        raise ValueError(f'Groups do not match! {annos[0].group} {new_annos[0].group}')
    merged = annos + new_annos
    merged_unique = sorted(set(merged), key=lambda a: a.updated)
    dupes = [sorted([a for a in merged_unique if a.id == id], key=lambda a: a.updated)
             for id, count in Counter(anno.id for anno in merged_unique).most_common()
             if count > 1]

    will_stay = [dupe[-1] for dupe in dupes]
    to_remove = [a for dupe in dupes for a in dupe[:-1]]

    la = len(annos)
    lm = len(merged)
    lmu = len(merged_unique)
    [merged_unique.remove(d) for d in to_remove]
    lmuc = len(merged_unique)

    print('added', lmuc - la, 'new annotations')

    get_annos.memoize_annos(merged_unique)

if __name__ == '__main__':
    main()
