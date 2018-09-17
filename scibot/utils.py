#!/usr/bin/env python3.6

import hashlib
import logging
import requests
from pyontutils.utils import Async, deferred, chunk_list, anyMembers
from IPython import embed


def DOI(doi):
    return 'https://doi.org/' + doi


def PMID(pmid):
    return pmid.replace('PMID:', 'https://www.ncbi.nlm.nih.gov/pubmed/')


def get_pmid_from_url(url):
    if anyMembers(url,
                  'www.ncbi.nlm.nih.gov/pubmed/',
                  'europepmc.org/abstract/MED/'):
        # TODO validate the suffix
        _, suffix = url.rsplit('/', 1)
        return 'PMID:' + suffix


def makeSimpleLogger(name):
    # TODO use extra ...
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()  # FileHander goes to disk
    formatter = logging.Formatter('[%(asctime)s] - %(levelname)s - %(name)s - %(message)s')  # TODO file and lineno ...
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    return logger


def group_to_memfile(group, post=lambda group_hash:None):
    m = hashlib.sha256()
    m.update(group.encode())
    group_hash = m.hexdigest()
    memfile = f'/tmp/annos-{group_hash}.pickle'
    post(group_hash)
    return memfile


def zap_deleted(get_annos):
    annos = get_annos()
    new_annos = get_annos.get_annos_from_api(len(annos), 200)
    n_deleted = len([a for a in new_annos if a in annos])
    print('there are', n_deleted, 'potentially deleted annotations')
    missing = []
    h = get_annos.h()

    def thing(id):
        return id, h.head_annotation(id).ok

    # work backwards to cull deleted annotations
    size = 500
    n_chunks = len(annos) // size
    for i, anno_chunk in enumerate(chunk_list(list(reversed(annos)), size)):
        if i < 10:
            continue
        print('chunk size', size, 'number', i + 1 , 'of', n_chunks, 'found', len(missing))
        if len(missing) >= n_deleted:
            break
        responses = Async(25)(deferred(thing)(a.id) for a in anno_chunk)
        missing += [id for id, ok in responses if not ok]

    # TODO actually remove them
    embed()


def resolution_chain(doi):
    doi = doi  # TODO
    s = requests.Session()
    head = requests.head(doi)
    yield head.url
    while head.is_redirect and head.status_code < 400:  # FIXME redirect loop issue
        yield head.next.url
        head = s.send(head.next)
        yield head.url
        if not head.is_redirect:
            break

    if head.status_code >= 400:
        raise LoadError(f'Nothing found at {self.name}\n')
