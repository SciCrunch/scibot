#!/usr/bin/env python3.6

import os
import pickle
import requests
from pyontutils.utils import noneMembers, anyMembers
from hyputils.hypothesis import HypothesisUtils, HypothesisAnnotation, HypothesisHelper, Memoizer
from export import api_token, username, group, group_public, bad_tags, get_proper_citation
from IPython import embed

if group_public == '__world__':
    raise IOError('WARNING YOU ARE DOING THIS FOR REAL PLEASE COMMENT OUT THIS LINE')

if group.startswith('5'):
    print('Real annos')
    memfile = '/tmp/real-scibot-annotations.pickle'
elif group.startswith('4'):
    print('Test annos')
    memfile = '/tmp/test-scibot-annotations.pickle'

get_annos = Memoizer(api_token, username, group, memoization_file=memfile)

def getPMID(tags):
    # because sometime there is garbage in the annotations
    ids = set()
    for t in tags:
        if t.startswith('PMID:') and t[5:].isnumeric():
            ids.add(t)
    if ids:
        if len(ids) > 1:
            raise ValueError('More than one PMID detected!')
        return list(ids)[0]

def getDOI(tags):
    ids = set()
    for t in tags:
        if t.startswith('DOI:'):
            ids.add(t)
    if ids:
        if len(ids) > 1:
            raise ValueError('More than one DOI detected!')
        return list(ids)[0]

def getIDS(tags):
    return getDOI(tags), getPMID(tags)
    
def resolve(rrid):
    return RRIDCuration.resolver + rrid

class mproperty:
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        if doc is None and fget is not None and hasattr(fget, "__doc__"):
            doc = fget.__doc__
        self.__get = fget
        self.__set = fset
        self.__del = fdel
        self.__doc__ = doc
        if fget is not None:
            self._attr_name = '___' + fget.__name__
    
    def __get__(self, inst, type=None):
        if inst is None:
            return self
        if self.__get is None:
            raise AttributeError('unreadable attribute')
        
        if not hasattr(inst, self._attr_name):
            result = self.__get(inst)
            setattr(inst, self._attr_name, result)
        return getattr(inst, self._attr_name)
    
    def __set__(self, inst, value):
        if self.__set is None:
            raise AttributeError('can\'t set attribute')
        delattr(inst, self._attr_name)
        return self.__set(inst, value)

    def __delete__(self, inst):
        if self.__del is None:
            raise AttributeError('can\'t delete attribute')
        delattr(inst, self._attr_name)
        return self.__del(inst)

def mproperty_set(inst, func_name, value):
    if isinstance(func_name, basestring):
        property_name = '___' + func_name
    elif hasattr(func_name, '__name__'):
        property_name = '___' + func_name.func_name
    else:
        raise
    setattr(inst, property_name, value)

class RRIDCuration(HypothesisHelper):
    resolver = 'http://scicrunch.org/resolver/'
    docs_link = 'http://scicrunch.org/resources'  # TODO update with explication of the tags
    REPLY_TAG = 'RRIDCUR:Released'
    #SKIP_DUPE_TAG = 'RRIDCUR:Duplicate-Released'  # sigh...
    SUCCESS_TAG = 'RRIDCUR:Released'
    INCOR_TAG = 'RRIDCUR:Incorrect' 
    CORR_TAG = 'RRIDCUR:Corrected'
    VAL_TAG = 'RRIDCUR:Validated'
    skip_tags = 'RRIDCUR:Duplicate', 'RRIDCUR:Unrecognized', *bad_tags
    skip_anno_tags = 'RRIDCUR:InsufficientMetadata',  # tags indicating that we should not release to public
    h_private = HypothesisUtils(username=username, token=api_token, group=group, max_results=100000)
    h_public = HypothesisUtils(username=username, token=api_token, group=group_public, max_results=100000)
    public_annos = {}  # for
    private_replies = {}  # in cases where a curator made the annotation
    objects = {}
    identifiers = {}  # paper id: {uri:, doi:, pmid:}
    _papers = {}
    _xmllib = {}
    _done_all = False
    known_bad = [
        #'UPhsBq-DEeegjsdK6CuueQ',
        #'UI4WWK95Eeea6a_iF0jHWg',
        #'HdNDhK93Eeem7sciBew4cw',
        #'TwobZK91Eee7P1c_azGIHA',
        #'ZdtjrK91EeeaLwfGBVmqcQ',
        #'KU1eDKh-EeeX9HMjEOC6rA',
        #'uvwscqheEeef8nsbQydcag',
        #'09rXMqVKEeeAuCfc1MOdeA',
        #'nBsIdqSHEee2Zr-s9njlHA',

        # max wat
        #'AVOVWIoXH9ZO4OKSlUhA',  # copy paste error
        #'nv_XaPiaEeaaYkNwLEhf0g',  # a dupe
        #'8lMPCAUoEeeyPXsJLLYetg',
                ]

    def __init__(self, anno, annos):
        super().__init__(anno, annos)
        if self._done_loading:
            if self._done_all:
                print('WARNING you ether have a duplicate annotation or your annotations are not sorted by updated.')
                #print(HypothesisHelper(anno, annos))
                #embed()
                #raise BaseException('WHY ARE YOU GETTING CALLED MULTIPLE TIMES?')
            self._fetch_xmls(os.path.expanduser('~/ni/scibot_rrid_xml.pickle'))
            self._do_papers()
            self.__class__._done_all = True

    @classmethod
    def _fetch_xmls(cls, file=None):
        if cls._done_loading:
            rrids = set(r.rrid for r in cls.objects.values() if r.rrid is not None)
            if file is not None:
                with open(file, 'rb') as f:
                    cls._xmllib = pickle.load(f)
            to_fetch = [rrid for rrid in rrids if rrid not in cls._xmllib]
            print(f'missing {len(to_fetch)} rrids')
            for rrid in to_fetch:
                url = cls.resolver + rrid + '.xml'
                print('fetching', url)
                resp = requests.get(url)
                cls._xmllib[rrid] = resp.content

    @classmethod
    def _do_papers(cls):
        papers = cls._papers
        if cls._done_loading:
            for i, o in cls.objects.items():
                if o.uri not in papers:
                    papers[o.uri] = {'DOI':None,
                                     'PMID':None,
                                     'nodes':{},
                                     'rrids':{}}
                if o._type == 'pagenote':
                    papers[o.uri]['DOI'], papers[o.uri]['PMID'] = getIDS(o._fixed_tags)
                        
                elif o.isAstNode:
                    if papers[o.uri]['PMID'] is None and o.rrid is None:
                        pmid = getPMID(o._fixed_tags)
                        papers[o.uri]['PMID'] = pmid
                        #if pmid is None:
                            #print(o)
                    else:
                        papers[o.uri]['nodes'][i] = o
                        if o.rrid not in papers[o.uri]['rrids']:
                            papers[o.uri]['rrids'][o.rrid] = {
                                'public_anno':None,
                                'objects':set(),
                            }
                        if o.isReleaseNode:
                            papers[o.uri]['rrids'][o.rrid]['objects'].add(o)

    @classmethod
    def _get_duplicates(cls):
        return [(p, r, rus)
                for p, v in cls._papers.items()
                for r, rus in v['rrids'].items()
                if len(rus['objects']) > 1]

    @classmethod
    def _adjudicate_duplicates(cls):
        objects = cls.objects
        papers = cls._papers
        rc = list(objects.values())
        asserted_dupes = [r for r in rc if 'RRIDCUR:Duplicate' in r._fixed_tags]
        adupes_that_arent = [r for r in asserted_dupes
                             if r.rrid not in [r2.rrid
                                               for idr2, r2 in r.paper['nodes'].items()
                                               if idr2 is not r.id]]
        not_dupes = [r for r in rc
                     if (r.isAstNode and
                         r.rrid is not None and
                         r.rrid not in [r2.rrid
                                        for idr2, r2 in r.paper['nodes'].items()
                                        if idr2 is not r.id])]

        dupes = [r for r in rc
                 if (r.isAstNode and
                     r.rrid is not None and
                     r.rrid in [r2.rrid
                                for idr2, r2 in r.paper['nodes'].items()
                                if idr2 is not r.id])]
        sets = {}
        for du in dupes:
            if du.uri not in sets:
                sets[du.uri] = {}
            di = sets[du.uri]
            if du.rrid not in di:
                di[du.rrid] = set()
            rdi = di[du.rrid]
            rdi.add(du)

        sd = sorted(dupes, key=lambda r:(r.uri, r._anno.updated))

        # in theory could update the mapping in objects...
        # probably better to create another class that functions on papers and RRIDs
        # instead of on annotations...

        #cls._duplicates_not_to_release = set()
        embed()

    @property
    def duplicates(self):
        if self.isReleaseNode and self.rrid is not None:
            return tuple(o for o in self.paper['rrids'][self.rrid]['objects'] if o is not self)
        else:
            return tuple()

    @property
    def isAstNode(self):
        if (self._type == 'annotation' and
            self._fixed_tags):
            return True
        else:
            return False

    @property
    def already_released_or_skipped(self):
        return any(anyMembers(r.tags, self.REPLY_TAG) for r in self.replies)

    @property
    def isReleaseNode(self):
        if anyMembers(self._fixed_tags, *self.skip_anno_tags):
            return False
        #elif self in self._duplicates_not_to_release:  # TODO post private reply to mark these
            #return False
        #elif 'RRIDCUR:Duplicate' in self._fixed_tags and not self.proper_citation:  # TODO remove?
            #return False
        elif (self.rrid is None and
              self._Missing and
              'RRID:' not in self._text):
            return False
        elif (self.isAstNode and not getPMID(self._fixed_tags) or
            self._type == 'pagenote' and getDOI(self._fixed_tags)):
            return True
        else:
            return False

    @property
    def _xml(self):
        if self._xmllib and self.rrid is not None:
            return self._xmllib[self.rrid]

    @property
    def paper(self):
        if self._done_loading:
            return self._papers[self.uri]

    @property
    def uri(self): return self._anno.uri

    @property
    def target(self): return self._anno.target

    @property
    def _Incorrect(self):
        return self.INCOR_TAG in self._fixed_tags

    @property
    def _Missing(self):
        return 'RRIDCUR:Missing' in self._fixed_tags

    @property
    def _Unrecognized(self):
        return 'RRIDCUR:Unrecognized' in self._fixed_tags

    @property
    def _Validated(self):
        return self.VAL_TAG in self._fixed_tags

    @property
    def alert(self):
        if not self.public_tags:
            return None
        elif self.INCOR_TAG in self.public_tags:
            return 'No record found.'  # if there is not a replacement RRID listed along with this tag then alert that we could find no RRID at all for this
        elif self.CORR_TAG in self.public_tags:
            return 'Identifier corrected.'
        else:
            return None

    @property
    def _original_rrid(self):
        # cannot call self.tags from here
        # example of case where I need to check for RRIDCUR:Incorrect to make the right determination
        "-3zMMjc7EeeTBfeviH2gHg"
        #https://hyp.is/-3zMMjc7EeeTBfeviH2gHg/www.sciencedirect.com/science/article/pii/S0896627317303069

        # TODO case where a curator highlights but there is no rrid but it is present in the reply

        # TODO case where unresolved an no replies

        maybe = [t for t in self._fixed_tags if t not in self.skip_tags and 'RRID:' in t]
        if maybe:
            if len(maybe) > 1:
                if self.id not in self.known_bad:
                    raise ValueError(f'More than one rrid in {maybe} \'{self.id}\' {self.shareLink}')
            if anyMembers(self._fixed_tags, *self.skip_anno_tags):
                # RRIDCUR:InsufficientMetadata RRIDs have different semantics...
                rrid = None
            else:
                rrid = maybe[0]
        elif 'RRIDCUR:Unresolved' in self._tags:  # scibot is a good tagger, ok to use _tags ^_^
            if not self.exact.startswith('RRID:'):
                rrid = 'RRID:' + self.exact
            else:
                rrid = self.exact
        elif ((self._Unrecognized or self._Validated) and
              'RRID:' not in self._text and
              self.exact):
            if 'RRID:' in self.exact:
                front, rest = self.exact.split('RRID:')
                rest = rest.replace(' ', '')
                rrid = 'RRID:' + rest  # yay for SCRRID:SCR_AAAAAAAHHHHH
            elif self.exact.startswith('AB_') or self.exact.startswith('IMSR_JAX'):
                rrid = 'RRID:' + self.exact.strip()
            else:
                rrid = None
        elif self._anno.user != self.h_private.username:
            # special case for the old practice of putting the correct rrid in the text instead of the tags
            if 'RRID:' in self._text:
                try:
                    junk, id_ = self._text.split('RRID:')
                except ValueError as e:
                    #print('too many RRIDs in text, skipping', self.shareLink, self._text)
                    id_ = 'lol lol'
                id_ = id_.strip()
                if ' ' in id_:  # not going to think to hard on this one
                    rrid = None
                else:
                    rrid = 'RRID:' + id_
            elif self.exact and self._Incorrect and self.exact.startswith('AB_'):
                rrid = 'RRID:' + self.exact
            else:
                rrid = None
        else:
            rrid = None

        return rrid
            
    @property
    def rrid(self):
        rrid = self._original_rrid

        # fix malformed RRIDs
        if rrid is not None:
            srrid = rrid.split('RRID:')
            if len(srrid) > 2:
                rrid = 'RRID:' + srrid[-1]

        # output logic
        if self._type == 'reply':
            return rrid
        elif self._type == 'annotation':
            reps = [r for r in self.replies if r.rrid]
            rtags = [t for r in self.replies for t in r.tags]
            if reps:
                if len(reps) > 1:
                    if len(set(r.rrid for r in reps)) == 1:
                        #print(f'WARNING multiple replies with the same rrid in {reps}')
                        pass  # too much
                    else:
                        raise ValueError(f'More than one rrid in {reps}')
                rep = reps[0]
                if self.CORR_TAG in rep.tags:
                    return rep.rrid
                elif rrid is None:
                    return rep.rrid
                elif self.INCOR_TAG in rep._fixed_tags:
                    return None
                elif (rrid is not None and
                      rep.rrid is not None and
                      rrid != rep.rrid):
                    return rep.rrid
            elif self.INCOR_TAG in rtags:
                return None
            return rrid

    @property
    def rridLink(self):
        if self.rrid:
            return self.resolver + self.rrid

    @property
    def corrected(self):
        if self._done_loading and self.rrid is not None:
            if self._original_rrid == self.rrid:
                if self.exact and self._original_rrid:
                    if self._Incorrect:
                        return self.rrid.strip('RRID:') in self.exact
            elif self._original_rrid is not None:
                return True

    @mproperty
    def proper_citation(self):
        if self.isAstNode and self.rrid:
            if self._xml is None:
                return 'XML was not fetched no citation included.'
            pc = get_proper_citation(self._xml)
            if not pc.startswith('(') and ' ' in pc:
                pc = f'({pc})'
            return pc

    @property
    def doi(self):
        if self._papers:
            return self._papers[self.uri]['DOI']

    @property
    def pmid(self):
        if self._papers:
            return self._papers[self.uri]['PMID']

    @property
    def public_id(self):
        if hasattr(self, '_public_anno') and self._public_anno is not None:
            return self._public_anno.id

    @property
    def public_user(self):
        return 'acct:' + self.h_public.username + '@hypothesis.is'

    @property
    def text(self):
        return self._text  # XXX short circuit
        reference = f'<p>Public Version: <a href=https://hyp.is/{self.public_id}>{self.public_id}</a></p>'
        if self._anno.user != self.h_private.username:
            return reference
        elif self.isAstNode:
            return reference + self._text
        else:
            return self._text 

    @property
    def private_text(self):
        if self.isReleaseNode and self.public_id:
            return shareLinkFromId(self.public_id)

    @mproperty
    def _curators(self):
        out = set()
        if self._anno.user != self.h_private.username:
            out.add(self._anno.user)
        if self.replies:
            for r in self.replies:
                out.update(r._curators)
        return out

    @mproperty
    def curators(self):
        return sorted(set((*self._curators, *(n
                                              for d in self.duplicates
                                              for n in d._curators))))

    @mproperty
    def _curator_notes(self):
        out = set()
        if self._text:
            if self._anno.user != self.h_private.username:
                out.add(self._text)
            if self._type == 'annotation':
                for r in self.replies:
                    out.update(r.curator_notes)
        return out

    @mproperty
    def curator_notes(self):
        return sorted(set((*self._curator_notes, *(n
                                                   for d in self.duplicates
                                                   for n in d._curator_notes))))

    @property
    def public_text(self):  # FIXME duplicates
        if self.isAstNode:

            ALERT = f'<p>{self.alert}</p>\n<hr>\n' if self.alert else ''
            curator_notes = ''.join(f'<p>Curator note: {cn}</p>\n' for cn in self.curator_notes)
            curator_note_text = f'{curator_notes}' if self.curator_notes else ''
            curators = ' '.join(f'@{c}' for c in self.curators)
            curator_text = f'<p>Curator: {curators}</p>\n' if self.curators else ''
            resolver_xml_link = f'{self.resolver}{self.rrid}.xml'
            nt2_link = f'http://nt2.net/{self.rrid}'
            idents_link = f'http://identifiers.org/{self.rrid}'
            links = (f'<p>Resource used:<br>\n{self.proper_citation}\n</p>\n'
                     f'<p>SciCrunch record: <a href={self.rridLink}>{self.rrid}</a><p>\n'
                     '<p>Alternate resolvers:<br>\n'
                     f'<a href={resolver_xml_link}>SciCrunch xml</a>\n'
                     f'<a href={nt2_link}>N2T</a>\n'
                     f'<a href={idents_link}>identifiers.org</a>\n'
                     '</p>') if self.rrid else ''

            second_hr = '<hr>\n' if ALERT and not (curator_text or curator_note_text or links) else ''
            return (f'{ALERT}'
                    f'{curator_text}'
                    f'{curator_note_text}'
                    f'{links}'
                    f'{second_hr}'
                    f'<p>\n<a href={self.docs_link}>What is this?</a>\n</p>')

    @property
    def _fixed_tags(self):
        # fix bad tags using the annotation-* tags
        if self.replies:  # TODO
            tags = [t for t in self._tags]
            for reply in self.replies:
                if 'annotation-tags:replace' in reply._tags:
                    tags = [t for t in reply._tags if t != 'annotation-tags:replace']
        else:
            tags = self._tags

        fixes = {'RRIDCUR:InsufficientMetaData':'RRIDCUR:InsufficientMetadata'}
        out_tags = []
        for tag in tags:
            if tag in bad_tags:
                tag = tag.replace('RRID:', 'RRIDCUR:')
            if tag in fixes:
                tag = fixes[tag]
            out_tags.append(tag)
        return out_tags

    @property
    def tags(self):
        tags = self._fixed_tags
        if self.isAstNode:
            return self._tags  # XXX short circuit
            if self._anno.user != self.h_private.username:
                if self.rrid:
                    return [self.REPLY_TAG]
                else:
                    return []
            else:
                return sorted(tags + [self.SUCCESS_TAG])
        elif self._type == 'reply':  # NOTE replies don't ever get put in public directly
            out_tags = []
            for tag in tags:
                if tag.startswith('RRID:'):
                    continue  # we deal with the RRID itself in def rrid(self)
                elif tag == self.INCOR_TAG and self.rrid:
                    continue
                else:
                    out_tags.append(tag)
            if self.corrected:
                out_tags.append(self.CORR_TAG)
            return sorted(out_tags)

    @property
    def private_tags(self):
        if self.isReleaseNode:
            return [self.REPLY_TAG]

    @property
    def public_tags(self):  # FIXME duplicates
        tags = set()
        for reply in self.replies:
            for tag in reply.tags:
                if tag not in self.skip_tags:
                    if self.corrected and tag == self.INCOR_TAG:
                        continue
                    tags.add(tag)
        for dupe in self.duplicates:
            for tag in dupe.tags:
                if tag not in self.skip_tags:
                    tags.add(tag)

        for tag in self._fixed_tags:
            if self.corrected and tag == self.INCOR_TAG:
                continue
            if tag in self.skip_tags:
                continue
            if not tag.startswith('RRID:'):
                tags.add(tag)
        if self.corrected:
            tags.add(self.CORR_TAG)
        if self.rrid:
            tags.add(self.rrid)
            if self._anno.user != self.h_private.username and self.VAL_TAG not in tags:
                tags.add(self.VAL_TAG)
        return sorted(tags)

    @property
    def public_payload(self):
        if self.isReleaseNode:
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
        #if self._anno.user != self.h_private.username:
        payload = {
            'group':self.h_private.group,
            'permissions':self.h_private.permissions,
            'references':[self.id],  # this matches what the client does
            'target':[{'source':self.uri}],
            'tags':self.private_tags,
            'text':self.private_text,
            'uri':self.uri,
        }
        #else:
            #payload = {
                #'tags':self.tags,
                #'text':self.text,
            #}

    @property
    def _public_anno(self):
        if self.rrid is None:
            #print('No RRID: will reset _public_anno after posting')
            return None
        else:
            pa = self.paper['rrids'][self.rrid]['public_anno']
            if pa is not None:
                return pa

    def post_public(self):
        if self._public_anno is not None:  # dupes of others may go first
            payload = self.public_payload  # XXX TODO
            if payload:
                response = self.h_public.post_annotation(payload)
                self._public_response = response
                anno = HypothesisAnnotation(response.json())
                if self.rrid is None:
                    self._public_anno = anno
                else:
                    self.paper['rrids'][self.rrid]['public_anno'] = anno
                self.public_annos[self._public_anno.id] = self._public_anno

    def reply_private(self):  # let's keep things immutable
        response = self.h_private.post_annotation(self.private_payload)

    def patch_private(self):  # XXX do not use unless you are really sure
        if self.public_id is not None:
            if self._anno.user != self.h_private.username:
                response = self.h_private.post_annotation(self.private_payload)
            else:
                response = self.h_private.patch_annotation(self.id, self.private_payload)
            self._private_response = response

    def __repr__(self, depth=0):
        start = '|' if depth else ''
        t = ' ' * 4 * depth + start

        parent_id =  f"\n{t}parent_id:    {self.parent.id} {self.__class__.__name__}.byId('{self.parent.id}')" if self.parent else ''
        uri_text =   f'\n{t}uri:          {self.uri}' if self.uri else ''
        doi_text =   f'\n{t}doi:          {self.doi}' if self.doi else ''
        pmid_text =  f'\n{t}pmid:         {self.pmid}' if self.pmid else ''
        rrid_text =  f'\n{t}rrid:         {self.rrid} {self.rridLink}' if self.rrid else ''
        exact_text = f'\n{t}exact:        {self.exact}' if self.exact else ''

        lp = f'\n{t}'

        _text_align = '_text:        '
        _text_line = lp + ' ' * len(_text_align)
        _text_text = lp + _text_align + self._text.replace('\n', _text_line) if self._text else ''

        text_align = 'text:         '
        text_line = lp + ' ' * len(text_align)
        text_text = lp + text_align + self.text.replace('\n', text_line) if self.text else ''

        _tag_text =  f'\n{t}_tags:        {self._tags}' if self._tags else ''
        tag_text =   f'\n{t}tags:         {self.tags}' if self.tags else ''

        prte_text =  f'\n{t}prtext:       {self.private_text}' if self.private_text else ''
        prta_text =  f'\n{t}prtags:       {self.private_tags}' if self.private_tags else ''

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
                f'\n{t}updated:      {self._anno.updated}'
                f'\n{t}user:         {self._anno.user}'
                f'\n{t}isAstNode:    {self.isAstNode}'
                f'\n{t}isRelNode:    {self.isReleaseNode}'
                f'{parent_id}'
                f'{uri_text}'
                f'{doi_text}'
                f'{pmid_text}'
                f'{rrid_text}'
                f'{exact_text}'
                f'{_text_text}'
                #f'{text_text}'
                f'{_tag_text}'
                f'{tag_text}'
                f'{prte_text}'
                f'{prta_text}'
                f'{ptext}'
                f'{ptag_text}'
                f'{replies_text}'
                f'\n{t}____________________')

# repl convenience
rrcu = RRIDCuration

def sanity_and_stats(rc):
    print('groups')
    rp = [r for r in rc if r.replies]
    rpt = [r for r in rp if any(re for re in r.replies if re._text)]
    rr = [r for r in rc if r.isReleaseNode]
    ns = [r for r in rc if r._anno.user != 'scibot']

    # sanity 
    unresolved = [r for r in rr if r.rrid and not r.proper_citation]

    incorrect_with_rrid = [r
                           for r in rc
                           if (r.isReleaseNode and
                               r.INCOR_TAG in r.public_tags and
                               r.rrid)]
    #dupes = [r for r in rc if 'RRIDCUR:Duplicate' in r._fixed_tags]

    # these seem to be from a strange use of RRIDCUR:Duplicate where
    # I would include the tag if there was another instance of the
    # RRID that was also found on the page????
    #dupes_that_arent = [r for r in dupes
                        #if r.rrid not in [r2.rrid
                                          #for idr2, r2 in r.paper['nodes'].items()
                                          #if idr2 is not r.id]]
    #visconf = [(r1.rrid, sorted(r.rrid for r in r1.paper['nodes'].values()))
               #for r1 in dupes_that_arent]
    #links = [r.shareLink for r in dupes_that_arent]

    papers = rrcu._papers.values()
    #paper_sanity = [paper for paper in papers
                    #if not (len(set(r.rrid for r in paper['nodes'].values() if r.isReleaseNode)) ==
                            #len([r.rrid for r in paper['nodes'].values() if r.isReleaseNode]))]

    report = report_gen(papers, unresolved)
    to_review_txt, to_review_html = to_review(unresolved)
    embed()

def report_gen(papers, unresolved):
    # reporting
    doi_papers = 0
    pmid_papers = 0
    both_papers = 0
    neither_papers = 0
    doio_papers = 0
    pmido_papers = 0
    for p in papers:
        if not (p['DOI'] or p['PMID']):
            neither_papers += 1
        else:
            if p['DOI']:
                doi_papers += 1
                if not p['PMID']:
                    doio_papers += 1
            if p['PMID']:
                pmid_papers += 1
                if not p['DOI']:
                    pmido_papers += 1
            if p['DOI'] and p['PMID']:
                both_papers += 1

    report = (
        'Paper id stats:\n'
        f'DOI:        {doi_papers}\n'
        f'PMID:       {pmid_papers}\n'
        f'Both:       {both_papers}\n'
        f'Neither:    {neither_papers}\n'
        f'DOI only:   {doio_papers}\n'
        f'PMID only:  {pmido_papers}\n'
        f'Total:      {len(papers)}\n'
        '\n'
        'Unresolved stats:\n'
        f'Total:         {len(unresolved)}\n'
        f'Unique RRIDs:  {len(set(r.rrid for r in unresolved))}\n'
    )

    with open('rridcur-report.txt', 'wt') as f:
        f.write(report)

    return report

def to_review(unresolved):
    to_review_txt = [f'{r.shareLink}    resolver:    {r.rridLink}\n' for r in unresolved]
    with open('unresolved-and-uncurated.txt', 'wt') as f:
        f.writelines(to_review_txt)

    to_review_html = (
        ['<style>table { font-family: Dejavu Sans Mono; font-size: 75%; }</style>\n'
         f'<p>Unresolved and uncurated {len(unresolved)}</p>\n'
         '<table>\n'] + 
        [(f'<tr><td><a href={r.shareLink}>{r.shareLink}</a></td>'
          '<td>resolver:</td>'
          f'<td><a href={r.rridLink}>{r.rridLink}</a></td><tr>\n')
         for r in sorted(unresolved, key=lambda u: (u.rrid, len(u.shareLink)))] +
        ['</table>']
    )
    with open('unresolved-and-uncurated.html', 'wt') as f:
        f.writelines(to_review_html)

    return to_review_txt, to_review_html

def clean_dupes(get_annos):
    annos = get_annos()
    seen = set()
    dupes = [a.id for a in annos if a.id in seen or seen.add(a.id)]
    preunduped = [a for a in annos if a.id in dupes]
    for id_ in dupes:
        print('=====================')
        anns = sorted((a for a in annos if a.id == id_), key=lambda a: a.updated)
        [print(a.updated, HypothesisHelper(a, annos)) for a in anns]
        for a in anns[:-1]:  # all but latest
            annos.remove(a)
    unduped = [a for a in annos if a.id in dupes]
    # get_annos.memoize_annos(annos)
    embed()

def main():
    from desc.prof import profile_me

    # clean updated annos
    #clean_dupes(get_annos)
    #return

    # loading
    annos = get_annos()
    #@profile_me
    #def load():
        #for a in annos:
            #rrcu(a, annos)
    #load()
    #rc = list(rrcu.objects.values())
    rc = [rrcu(a, annos) for a in annos]

    # sanity checks
    #print('repr everything')
    #_ = [repr(r) for r in rc]  # exorcise the spirits  (this is the slow bit, joblib breaks...)
    stats = sanity_and_stats(rc)

if __name__ == '__main__':
    main()

