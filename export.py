#!/usr/bin/env python3
from __future__ import print_function
import re
import csv
import pickle
from os import environ
from datetime import date
from collections import defaultdict
from collections import namedtuple, defaultdict
import requests
from lxml import etree
from hyputils.hypothesis import HypothesisUtils, HypothesisAnnotation, HypothesisHelper, Memoizer

api_token = environ.get('RRIDBOT_API_TOKEN', 'TOKEN')  # Hypothesis API token
username = environ.get('RRIDBOT_USERNAME', 'USERNAME') # Hypothesis username
group = environ.get('RRIDBOT_GROUP', '__world__')
group_public = environ.get('RRIDBOT_GROUP_PUBLIC', '__world__')
print(api_token, username, group)  # sanity check

get_annos = Memoizer(api_token, username, group, memoization_file='/tmp/scibot-annotations.pickle')

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
    h = HypothesisUtils(username=username, token=api_token, group=group, max_results=100000)
    params = {'group' : h.group }
    rows = h.search_all(params)
    annos = [HypothesisAnnotation(row) for row in rows]
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

bad_tags = {
    'RRID:Incorrect',
    'RRID:InsufficientMetadata',
    'RRID:Missing',
    'RRID:Unrecognized',
    'RRID:Unresolved',
    'RRID:Validated',
    'RRID:Duplicate',
}

def export_json_impl():
    h = HypothesisUtils(username=username, token=api_token, group=group, max_results=100000)
    params = {'group' : h.group }
    rows = h.search_all(params)
    annos = [HypothesisAnnotation(row) for row in rows]

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

class RRIDCuration(HypothesisHelper):
    resolver = 'http://scicrunch.org/resolver/'
    REPLY_TAG = 'RRIDCur:Released-Parent'
    SUCCESS_TAG = 'RRIDCur:Released'
    h_private = HypothesisUtils(username=username, token=api_token, group=group, max_results=100000)
    h_public = HypothesisUtils(username=username, token=api_token, group=group_public, max_results=100000)
    public_annos = {}  # for
    private_replies = {}  # in cases where a curator made the annotation
    objects = {}

    @property
    def uri(self): return self._anno.uri

    @property
    def target(self): return self._anno.target

    @property
    def rrid(self):  # FIXME
        maybe = [t for t in self.tags if 'RRID:' in t]
        if maybe:
            return maybe[0]

    @property
    def isAstNode(self):
        if self._type == 'annotation' and self.rrid:
            return True
        else:
            return False

    @property
    def proper_citation(self):
        if self.isAstNode:
            if not hasattr(self, '_xml'):
                resp = requests.get(self.resolver + self.rrid + '.xml')
                self._xml = resp.content
            return get_proper_citation(self._xml)

    @property
    def doi(self):
        return None  # TODO

    @property
    def pmid(self):
        return None  # TODO

    @property
    def public_id(self):
        if hasattr(self, '_public_anno') and self._public_anno is not None:
            return self._public_anno.id

    @property
    def public_user(self):
        return 'acct:' + self.h_public.username + '@hypothesis.is'

    @property
    def public_tags(self):
        if self._anno.user != self.h_private.username:
            if self.rrid:
                return [self.rrid, 'RRIDCur:Validated']
        else:
            add_tags = []
            for reply in self.replies:
                add_tags += reply._tags
            return self._tags + add_tags

    @property
    def public_text(self):
        if self.isAstNode:
            resolver_link = f'{self.resolver}{self.rrid}'
            resolver_xml_link = f'{self.resolver}{self.rrid}.xml'
            nt2_link = f'http://nt2.net/{self.rrid}'
            idents_link = f'http://identifiers.org/{self.rrid}'
            return (f'<h1>{self.proper_citation}</h1>\n'
                    f'<p><a href={resolver_link}></a>{self.rrid}<p>\n'
                    f'<p><a href={resolver_xml_link}></a>SciCrunch xml<p>\n'
                    f'<p><a href={nt2_link}></a>N2T resolver<p>\n'
                    f'<p><a href={idents_link}></a>identifiers.org resolver<p>')

    @property
    def tags(self):
        if self._anno.user != self.h_private.username:
            return [self.REPLY_TAG]
        else:
            return self._tags + [self.SUCCESS_TAG]

    @property
    def text(self):
        reference = f'<p>Public Version: <a href=https://hyp.is/{self.public_id}>{self.public_id}</a></p>'
        if self._anno.user != self.h_private.username:
            return reference
        else:
            return reference + self._text

    @property
    def public_payload(self):
        if self.isAstNode:
            return {
                'uri':self.uri,
                'target':self.target,
                'group':self.h_public.group,
                'user':self.public_user,
                'permissions':self.h_public.permissions,
                'tags':self.public_tags,
                'text':self.public_text,
            }

    @property
    def private_payload(self):
        if self._anno.user != self.h_private.username:
            payload = {
                'group':self.h_private.group,
                'permissions':self.h_private.permissions,
                'references':[self.id],  # this matches what the client does
                'target':[{'source':self.uri}],
                'tags':self.tags,
                'text':self.text,
                'uri':self.uri,
            }
        else:
            payload = {
                'tags':self.tags,
                'text':self.text,
            }

    def post_public(self):
        payload = self.public_payload
        if payload:
            response = h_public.post_annotation(payload)
            self._public_response = response
            self._public_anno = HypothesisAnnotation(response)
            self.cls.public_annos[self._public_anno.id] = self._public_anno

    def patch_private(self):
        if self.public_id is not None:
            if self._anno.user != self.h_private.username:
                response = h_private.post_annotation(self.private_payload)
            else:
                response = h_private.patch_annotation(self.id, self.private_payload)
            self._private_response = response

    def __repr__(self, depth=0):
        start = '|' if depth else ''
        t = ' ' * 4 * depth + start

        parent_id =  f"\n{t}parent_id:    {self.parent.id} {self.__class__.__name__}.byId('{self.parent.id}')" if self.parent else ''
        exact_text = f'\n{t}exact:        {self.exact}' if self.exact else ''

        text_align = 'text:         '
        lp = f'\n{t}'
        text_line = lp + ' ' * len(text_align)
        text_text = lp + text_align + self.text.replace('\n', text_line) if self.text else ''

        tag_text =   f'\n{t}tags:         {self.tags}' if self.tags else ''

        ptag_text =  f'\n{t}ptags:        {self.public_tags}' if self.public_tags else ''

        ptext_align = 'ptext:        '
        lp = f'\n{t}'
        ptext_line = lp + ' ' * len(ptext_align)
        ptext = lp + ptext_align + self.public_text.replace('\n', ptext_line) if self.public_text else ''

        replies = ''.join(r.__repr__(depth + 1) for r in self.replies)
        rep_ids = f'\n{t}replies:      ' + ' '.join(f"{self.__class__.__name__}.byId('{r.id}')"
                                                    for r in self.replies)
        replies_text = (f'\n{t}replies:{replies}' if self.reprReplies else rep_ids) if replies else ''
        return (f'\n{t.replace("|","")}*--------------------'
                f"\n{t}{self.__class__.__name__ + ':':<14}{self.shareLink} {self.__class__.__name__}.byId('{self.id}')"
                f'\n{t}user:         {self._anno.user}'
                f'\n{t}isAstNode:    {self.isAstNode}'
                f'{parent_id}'
                f'{exact_text}'
                f'{text_text}'
                f'{tag_text}'
                f'{ptext}'
                f'{ptag_text}'
                f'{replies_text}'
                f'\n{t}____________________')

def public_dump():
    from IPython import embed
    annos = get_annos()
    rc = [RRIDCuration(a, annos) for a in annos]
    embed()

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
    public_dump()
    return
    import json
    output_json, DATE = export_json_impl()
    with open('RRID-data-%s.json' % DATE, 'wt') as f:
        json.dump(output_json, f, sort_keys=True, indent=4)

if __name__ == '__main__':
    main()

