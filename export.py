#!/usr/bin/env python3
from __future__ import print_function
import re
import csv
from os import environ
from datetime import date
from collections import defaultdict
from hypothesis import HypothesisUtils, HypothesisAnnotation
from collections import namedtuple, defaultdict

api_token = environ.get('RRIDBOT_API_TOKEN', 'TOKEN')  # Hypothesis API token
username = environ.get('RRIDBOT_USERNAME', 'USERNAME') # Hypothesis username
group = environ.get('RRIDBOT_GROUP', '__world__')

print(api_token, username, group)  # sanity check

def export_impl():
    h = HypothesisUtils(username=username, token=api_token, group=group, max_results=5000)
    params = {'group' : h.group }
    rows = h.search_all(params)
    annos = [HypothesisAnnotation(row) for row in rows]
    annotated_urls = defaultdict(list)
    for anno in annos:
        annotated_urls[anno.uri].append(anno)

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
                    raise BaseException('more than one pmid tag')
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
        for anno in annos:
            RRID = None
            additional = []
            for tag in anno.tags:
                if re.match('RRID:.+[0-9]+', tag):  # ARRRRGGGGHHHHHHH ARRRRGGHHHH
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
                RRIDs[RRID].extend(additional)
                if anno.id in replies:
                    for r_anno in replies[anno.id]:
                        RRIDs[RRID].extend(r_anno.tags)  # not worrying about the text here

        for rrid, more in RRIDs.items():
            if not more:
                row = [PMID, rrid, None, annotated_url]
                output_rows.append(row)
            else:
                for val in set(more):  # cull dupes
                    row = [PMID, rrid, val, annotated_url]
                    output_rows.append(row)

    DATE = date.today().strftime('%Y-%m-%d')
    return output_rows, DATE

def main():
    output_rows, DATE = export_impl()
    with open('RRID-data-%s.csv' % DATE, 'wt') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerows(sorted(output_rows))

if __name__ == '__main__':
    main()

