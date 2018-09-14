#!/usr/bin/env python3
from __future__ import print_function
import re
import csv
import pickle
from datetime import date
from collections import defaultdict
from collections import namedtuple, defaultdict
from lxml import etree
from hyputils.hypothesis import HypothesisUtils, HypothesisAnnotation, Memoizer
from scibot.core import memfile, api_token, username, group

bad_tags = {
    'RRID:Incorrect',
    'RRID:InsufficientMetadata',
    'RRID:Missing',
    'RRID:Unrecognized',
    'RRID:Unresolved',
    'RRID:Validated',
    'RRID:Duplicate',
}

def get_proper_citation(xml):
    root = etree.fromstring(xml)
    if root.findall('error'):
        proper_citation = ''
    else:
        data_elements = root.findall('data')[0]
        data_elements = [(e.find('name').text, e.find('value').text) for e in data_elements]  # these shouldn't duplicate
        a = [v for n, v in data_elements if n == 'Proper Citation']
        proper_citation = a[0] if a else ''

    return proper_citation

def fix_trailing_slash(annotated_urls):
    for key in [k for k in annotated_urls.keys()]:
        if key.endswith('/'):
            new_key = key.rstrip('/')
            print(new_key)
            if new_key in annotated_urls:
                annotated_urls[key].extend(annotated_urls.pop(new_key))

def export_impl():
    get_annos = Memoizer(memfile, username=username, api_token=api_token, group=group)
    annos = get_annos()

    annotated_urls = defaultdict(list)
    for anno in annos:
        annotated_urls[anno.uri].append(anno)

    fix_trailing_slash(annotated_urls)

    output_rows = []
    for annotated_url in annotated_urls.keys():
        #print(annotated_url)
        annos = annotated_urls[annotated_url]
        replies = defaultdict(list)
        PMID = []
        for anno in annos:  # gotta build the reply structure and get pmid
            #print('id:', anno.id)
            #print('user:', anno.user)
            #print('exact:', anno.exact)
            #print('text:', anno.text)
            #print('tags:', anno.tags)
            #print('type:', anno.type)
            #print('references:', anno.references)
            if anno.references:
                for reference in anno.references:  # shouldn't there only be one???
                    replies[reference].append(anno)
            PMID.extend([tag for tag in anno.tags if tag.startswith('PMID:') and '_' not in tag])  # bad tags with PMID:SCR_
            #curators didn't put the pmid in as tags :(
            if anno.text.startswith('PMID:'):  # DANGER ZONE
                if '_' in anno.text:
                    print('PMIDS DONT HAVE UNDERSCORES PROBABLY CURATION BUG', anno.text)
                else:
                    PMID.append(anno.text.strip())  # because, yep, when you don't tag sometimes you get \n :/

        if PMID:
            if len(PMID) > 1:
                print(PMID, annotated_url)
                if PMID[0] == PMID[1]:
                    PMID = PMID[0]
                    print('WARNING: more than one pmid tag')
                else:
                    print("raise BaseException('more than one pmid tag')")  # irritating
                    PMID = PMID[0]  # FIXME
            else:
                PMID = PMID[0]
                #print(PMID)
        else:
            all_tags = []
            for a in annos:
                all_tags.extend(a.tags)
            #print('NO PMID FOR', annotated_url)
            #print(set([a.user for a in annos]))
            #print(all_tags)
            PMID = annotated_url

        RRIDs = defaultdict(list)
        EXACTs = {}
        CITEs = {}
        #USERs = {}
        for anno in annos:
            RRID = None
            additional = []
            for tag in anno.tags:
                if re.match('RRID:.+[0-9]+.+', tag):  # ARRRRGGGGHHHHHHH ARRRRGGHHHH
                #if re.match('RRID:.+', tag):  # ARRRRGGGGHHHHHHH ARRRRGGHHHH
                    if RRID is not None:
                        raise BaseException('MORE THAN ONE RRID PER ENTRY!')
                    RRID = tag  # :/ this works for now but ARHGHHGHASFHAS
                else:
                    additional.append(tag)  # eg Unresolved

                if tag == 'RRIDCUR:Missing':  # fix for bad curation process
                    maybe_rrid = anno.text.strip()
                    if re.match('RRID:.+[0-9]+', maybe_rrid):  # ARRRRGGGGHHHHHHH ARRRRGGHHHH
                        RRID = maybe_rrid  # RRIDCUR:Missing was already added above

            if RRID is not None:
                EXACTs[RRID] = anno.exact.strip() if anno.exact else ''
                RRIDs[RRID].extend(additional)
                #USERs[RRID] = anno.user
                if RRID not in CITEs:
                    if anno.text:
                        if 'Proper Citation:' in anno.text:
                            CITEs[RRID] = anno.text.split('Proper Citation:')[1].strip().split('<',1)[0]

                if anno.id in replies:
                    for r_anno in replies[anno.id]:
                        RRIDs[RRID].extend(r_anno.tags)  # not worrying about the text here
            elif not anno.references and PMID not in anno.tags:  # this is an independent annotation which will not be included
                new = 'NONE:' + anno.id
                RRIDs[new].append('')
                EXACTs[new] = anno.exact
                #USERs[RRID] = anno.user

        for rrid, more in RRIDs.items():
            #FIXME TOOOOOO SLOW
            #r = requests.get('https://scicrunch.org/resolver/{RRID}.xml'.format(RRID=rrid))
            #if r.status_code < 300:
                #proper_citation = get_proper_citation(r.content)
            #else:
                #proper_citation = ''

            try:
                proper_citation = CITEs[rrid]
            except KeyError:  # FIXME this is a hack to avoid some cases of LWW for citations
                proper_citation = ''

            if not more:
                row = [PMID, rrid, '', annotated_url, EXACTs[rrid], proper_citation]
                output_rows.append(row)
            else:
                for val in set(more):  # cull dupes
                    row = [PMID, rrid, val, annotated_url, EXACTs[rrid], proper_citation]
                    output_rows.append(row)

    DATE = date.today().strftime('%Y-%m-%d')
    return output_rows, DATE

def export_json_impl():
    get_annos = Memoizer(memfile, username=username, api_token=api_token, group=group)
    annos = get_annos()

    # clean up bugs from old curation workflow
    for anno in annos:
        if anno.tags:
            new_tags = []
            for tag in anno.tags:
                if tag in bad_tags:
                    new_tags.append(tag.replace('RRID:', 'RRIDCUR:'))  # scibot made a mistake early, might be able to correct tags in bulk someday
                else:
                    new_tags.append(tag)  # horribly inefficient...
            anno.tags = new_tags

        if anno.text.startswith('RRID:'):  # catch cases where the RRID was put in text instead of in tags
            if 'RRIDCUR:Missing' in anno.tags or 'RRIDCUR:Unrecognized' in anno.tags:
                rtag = anno.text.split(None,1)[0]  # trap for cases where there is more text after an RRID...
                if rtag not in anno.tags:
                    anno.tags.append(rtag)
                    print('TEXT ISSUE for %s at https://hyp.is/%s' % (anno.user, anno.id))
        elif anno.exact and anno.exact.startswith('RRID:'):  # this needs to go second in case of RRIDCUR:Incorrect
            if anno.exact.startswith('RRID: '):  # deal with nospace first
                rtag = anno.exact.replace('RRID: ', 'RRID:')
            else:
                rtag = anno.exact
            rtag = rtag.split(None,1)[0]  # trap more
            if rtag not in anno.tags:
                if anno.user == 'scibot' and len(anno.tags) == 1 and anno.tags[0].startswith('RRID:RRID:'):  # FIXME HACK
                    anno.tags = [rtag]
                else:
                    pass  # anything else we detect in the data doesn't need to be corrected or used to fix tags

    output_json = [anno.__dict__ for anno in annos]
    DATE = date.today().strftime('%Y-%m-%d')
    return output_json, DATE

### URG

def oldmain():
    output_rows, DATE = export_impl()
    with open('RRID-data-%s.csv' % DATE, 'wt') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerows(sorted(output_rows))

    import json
    output_json, DATE = export_json_impl()
    with open('RRID-data-%s.json' % DATE, 'wt') as f:
        json.dump(output_json, f, sort_keys=True, indent=4)

def main():
    import json
    output_json, DATE = export_json_impl()
    with open('RRID-data-%s.json' % DATE, 'wt') as f:
        json.dump(output_json, f, sort_keys=True, indent=4)

if __name__ == '__main__':
    main()

