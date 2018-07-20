#!/usr/bin/env python3.6

import os
import pickle
import subprocess
from datetime import datetime
from urllib.parse import quote
from collections import defaultdict
import requests
from bs4 import BeautifulSoup
from pyontutils.utils import noneMembers, anyMembers, allMembers
from hyputils.hypothesis import HypothesisUtils, HypothesisAnnotation, HypothesisHelper, Memoizer, idFromShareLink, shareLinkFromId
from scibot.export import api_token, username, group, group_staging, bad_tags, get_proper_citation
from scibot.rrid import getDoi, get_pmid, annotate_doi_pmid
from IPython import embed

READ_ONLY = True
if group_staging == '__world__' and not READ_ONLY:
    raise IOError('WARNING YOU ARE DOING THIS FOR REAL PLEASE COMMENT OUT THIS LINE')

if group.startswith('5'):
    print('Real annos')
    memfile = '/tmp/real-scibot-annotations.pickle'
elif group.startswith('4'):
    print('Test annos')
    memfile = '/tmp/test-scibot-annotations.pickle'

get_annos = Memoizer(memfile, api_token, username, group, 200000)
get_pannos = Memoizer('/tmp/scibot-public-annos.pickle', api_token, username, group_staging)

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
    return Curation.resolver + rrid

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

class KeyAccessor:
    # XXX whenever annos changes these need to be recreated as well...
    # if that is too slow then we will need to implement proper add
    # and delete for only affected items...
    """ For when your identifiers aren't python compatible. """
    prop = 'id'
    object_container_class = set
    def __init__(self, objects=tuple(), id_prop=None):
        self._propagate = issubclass(self.object_container_class, KeyAccessor)
        self._objects = {}
        for o in objects:
            k = getattr(o, self.prop)
            if k not in self._objects:
                self._objects[k] = self._make_cont()
            self._objects[k].add(o)

        self._id_prop = None
        if id_prop is not None:
            if objects:
                print('setting id prop')
                setattr(self, id_prop, getattr(o, id_prop))  # o from the for loop
            else:
                self._id_prop = id_prop

    def _make_cont(self):
        if self._propagate:
            cont = self.object_container_class(id_prop=self.prop)
        else:
            cont = self.object_container_class()
        return cont

    def remove(self, object_):
        k = getattr(object_, self.prop)
        self._objects[k].remove(object_)
        if not self._objects[k]:
            self._objects.pop(k)

    def discard(self, object_):
        k = getattr(object_, self.prop)
        self._objects[k].discard(object_)
        if not self._objects[k]:
            self._objects.pop(k)

    def add(self, object_):
        if self._id_prop is not None:
            setattr(self, self._id_prop, getattr(object_, self._id_prop))
            self._id_prop = None
        k = getattr(object_, self.prop)
        if k not in self._objects:
            self._objects[k] = self._make_cont()

        self._objects[k].add(object_)

    def keys(self):
        return sorted(self._objects, key=lambda k: '0' if k is None else k)

    def values(self):
        for v in self._objects.values():
            yield v

    def items(self):
        for k, v in self._objects.items():
            yield k, v

    def __iter__(self):
        for k in self._objects:
            yield k

    def __contains__(self, key):
        return key in self._objects

    def __getitem__(self, key):
        try:
            return self._objects[key]
        except KeyError:
            self.__missing__(key)

    #def __setitem__(self, key):
        #raise TypeError('Cannot set values on this class, it is immutable')

    def __missing__(self, key):
        raise KeyError(f'{key} not found')

    def __len__(self):
        return len(self._objects)

    def __repr__(self):
        return repr({k:v for k,v in self.items()})

    def __str__(self):
        return str({k:v for k,v in self.items()})


class RRIDs(KeyAccessor):
    """ AKA a Paper """
    prop = 'rrid'
    object_container_class = set

    @property
    def doi(self):
        if None in self._objects:
            for o in self._objects[None]:
                if o._type == 'pagenote':  # FIXME some curators did these as annotations too...
                    for t in o.tags:
                        if t.startswith('DOI:'):
                            return t

    @property
    def pmid(self):
        if None in self._objects:
            for o in self._objects[None]:
                for t in o.tags:
                    if t.startswith('PMID:'):
                        return t

class Papers(KeyAccessor):
    prop = 'uri'
    object_container_class = RRIDs


class SameDOI(KeyAccessor):
    prop = 'doi'
    object_container_class = Papers


class SamePMID(KeyAccessor):
    prop = 'pmid'
    object_container_class = Papers


class PublicParagraphTags:
    Alert = 'alert'
    CuratorNote = 'curator-note'
    Curators = 'curators'
    Citation = 'inline-citation'
    Res = 'main-resolver'
    AltRes = 'alt-resolvers'
    Docs = 'documentation'
    CurLinks = 'curation-links'

class RRIDAnno(HypothesisHelper):
    resolver = 'http://scicrunch.org/resolver/'
    REPLY_TAG = 'RRIDCUR:Released'
    #SKIP_DUPE_TAG = 'RRIDCUR:Duplicate-Released'  # sigh...
    SUCCESS_TAG = 'RRIDCUR:Released'
    INCOR_TAG = 'RRIDCUR:Incorrect' 
    CORR_TAG = 'RRIDCUR:Corrected'
    VAL_TAG = 'RRIDCUR:Validated'
    skip_tags = 'RRIDCUR:Duplicate', 'RRIDCUR:Unrecognized', *bad_tags
    _annos = {}
    objects = {}
    _papers = None
    _done_all = False

    def __init__(self, anno, annos):
        super().__init__(anno, annos)
        if self._done_loading:
            if self._papers is None:
                self.__class__._papers = Papers(self.objects.values())
            else:  # FIXME... this could fail...
                self.__class__._papers.add(self)
            self.__class__._done_all = True

    @mproperty
    def created(self): return self._anno.created

    @mproperty
    def user(self): return self._anno.user

    @mproperty
    def uri(self): return self._anno.uri

    @mproperty
    def target(self): return self._anno.target

    @property
    def _fixed_tags(self):
        # fix bad tags using the annotation-* tags
        if 'annotation-tags:replace' in self._tags:
            return []  # these replies should be treated as invisible
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

    @mproperty
    def _Incorrect(self):
        return self.INCOR_TAG in self._fixed_tags

    @mproperty
    def _InsufficientMetadata(self):
        return 'RRIDCUR:InsufficientMetadata' in self._fixed_tags

    @mproperty
    def _Missing(self):
        return 'RRIDCUR:Missing' in self._fixed_tags

    @mproperty
    def _NotRRID(self):
        return 'RRIDCUR:NotRRID' in self._fixed_tags

    @mproperty
    def NotRRID(self):
        return bool([r for r in self.replies if r._NotRRID]) or self._NotRRID

    @mproperty
    def _Unrecognized(self):
        return 'RRIDCUR:Unrecognized' in self._fixed_tags

    @mproperty
    def _Validated(self):
        return self.VAL_TAG in self._fixed_tags

    @mproperty
    def Validated(self):
        return bool([r for r in self.replies if r._Validated]) or self._Validated

    @property
    def paper(self):
        if self._done_loading:
            return self._papers[self.uri]

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
                if self.id:
                    raise ValueError(f'More than one rrid in {maybe} \'{self.id}\' {self.shareLink}')
            if self._InsufficientMetadata:
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
        elif self._anno.user != self.h_curation.username:
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
        reps = sorted([r for r in self.replies if r.rrid], key=lambda r: r._anno.updated)
        rtags = [t for r in self.replies for t in r.tags]
        if self._type == 'reply':
            if reps:
                return reps[0].rrid  # latest RRID tag gets precidence  # FIXME bad if the other chain more recent... need to propatage updated...
            else:
                return rrid
        elif self._type == 'annotation':
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


class PublicAnno(RRIDAnno):  # TODO use this to generate the annotation in the first place
    staging_group = group_staging
    release_group = '__world__'
    h_staging = HypothesisUtils(username=username, token=api_token, group=group_staging, max_results=100000)
    _annos = {}
    objects = {}
    _papers = None

    def __init__(self, anno, annos):
        super().__init__(anno, annos)

    @classmethod
    def getByUriRrid(cls, uri, rrid):
        if cls._papers is None:
            raise ValueError('PublicAnno has not been loaded yet!')
        r = cls._papers[uri][rrid]
        if r:
            if len(r) > 1:
                raise TypeError('ERROR: Duplicate public annotation on RRID paper!')
            else:
                return next(iter(r))

    @property
    def curation_ids(self):
        soup = BeautifulSoup(self._text, 'lxml')  # FIXME etree?
        p = soup.find('p', {'id':'curation-links'})
        if p is not None:
            return [idFromShareLink(a['href']) for a in p.find_all('a')]
        else:
            return []

    @property
    def curation_annos(self):
        return [Curation.byId(i) for i in self.curation_ids]

    @property
    def curation_paper(self):
        if Curation._done_loading:
            for a in self.curation_annos:
                return a.paper

    @property
    def release_permissions(self):
        out = self._permissions  # safe since the dict is copied by HypothesisAnnotation
        out['read'] = ['group:' + self.release_group]
        return out

    @property
    def _release_payload(self):
        payload = {'group':self.release_group,
                   'permissions':self.release_permissions}
        return payload

    def release__world__(self):
        print('This has not been implemented in api yet.')
        return None
        if READ_ONLY:
            print('WARNING: READ_ONLY is set no action taken')
        else:
            r = self.h_staging.patch_annotation(self.id, self._release_payload)
            self._release_record = r
            return r

    def unrelease__world__(self):
        print('This has not been implemented in api yet.')
        return None
        if READ_ONLY:
            print('WARNING: READ_ONLY is set no action taken')
        else:
            if hasattr(self, '_release_record') or self._anno.group == self.release_group:
                payload = {'group':self.staging_group,
                           'permissions':self._permissions}
                r = self.h_staging.patch_annotation(self.id, payload)
                self._unrelease_record = r
                return r

    def __repr__(self, depth=0):
        start = '|' if depth else ''
        t = ' ' * 4 * depth + start

        lp = f'\n{t}'
        idp = 'curation_ids: '
        indent = lp + ' ' * len(idp)
        pid_text = lp + idp + indent.join(f"{shareLinkFromId(i)} Curation.byId('{i}')"
                                          for i in self.curation_ids)

        string = (f'{pid_text}\n'
                 )
        #return HypothesisHelper.__repr__(self, depth=depth, format__repr__for_children=string)
        return super().__repr__(depth=depth, format__repr__for_children=string)


class Curation(RRIDAnno):
    docs_link = 'https://scicrunch.org/resources/about/scibot'  # TODO update with explication of the tags
    skip_users = 'mpairish',
    h_curation = HypothesisUtils(username=username, token=api_token, group=group, max_results=200000)
    h_staging = PublicAnno.h_staging
    private_replies = {}  # in cases where a curator made the annotation
    _annos = {}
    objects = {}
    identifiers = {}  # paper id: {uri:, doi:, pmid:}
    _rrids = {}
    _xmllib = {}
    maybe_bad = [
        'UPhsBq-DEeegjsdK6CuueQ',
        'UI4WWK95Eeea6a_iF0jHWg',
        'HdNDhK93Eeem7sciBew4cw',
        'TwobZK91Eee7P1c_azGIHA',
        'ZdtjrK91EeeaLwfGBVmqcQ',
        'KU1eDKh-EeeX9HMjEOC6rA',
        'uvwscqheEeef8nsbQydcag',
        '09rXMqVKEeeAuCfc1MOdeA',
        'nBsIdqSHEee2Zr-s9njlHA',

        # max wat
        'AVOVWIoXH9ZO4OKSlUhA',  # copy paste error
        'nv_XaPiaEeaaYkNwLEhf0g',  # a dupe
        '8lMPCAUoEeeyPXsJLLYetg',
                ]

    def __init__(self, anno, annos):
        super().__init__(anno, annos)
        if self._done_loading:
            if not self._done_all:  # pretty sure this is obsolete?
                print('WARNING you ether have a duplicate annotation or your annotations are not sorted by updated.')
            #self._fetch_xmls(os.path.expanduser('~/ni/dev/rrid/scibot/scibot_rrid_xml.pickle'))
                #print(HypothesisHelper(anno, annos))
                #embed()
                #raise BaseException('WHY ARE YOU GETTING CALLED MULTIPLE TIMES?')
            #self._do_papers()

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

    @property
    def duplicates(self):
        if self.isReleaseNode and self.rrid is not None:
            return tuple(o for o in self.paper[self.rrid] if o is not self)
        else:
            return tuple()

    @property
    def isAstNode(self):
        if self._anno.user in self.skip_users:
            return False
        elif (self._type == 'annotation' and
            self._fixed_tags):
            return True
        else:
            return False

    @property
    def replies(self):
        return set(r for r in super().replies if r._anno.user not in self.skip_users)

    @property
    def already_released_or_skipped(self):
        return any(anyMembers(r.tags, self.REPLY_TAG) for r in self.replies)

    @property
    def isReleaseNode(self):
        if self._InsufficientMetadata:
            return False
        elif self.NotRRID:
            return False
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
    def alert(self):
        if not self.public_tags:
            return None
        elif self.INCOR_TAG in self.public_tags:
            return 'No record found.'  # if there is not a replacement RRID listed along with this tag then alert that we could find no RRID at all for this
        elif self.CORR_TAG in self.public_tags:
            return 'Identifier corrected.'
        else:
            return None

    @mproperty
    def corrected(self):
        if self._done_loading and self.rrid is not None:
            if self._original_rrid == self.rrid:
                if self.exact and self._original_rrid:
                    if self._Incorrect:
                        return self.rrid.strip('RRID:') not in self.exact
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
            return self._papers[self.uri].doi

    @property
    def pmid(self):
        if self._papers:
            return self._papers[self.uri].pmid

    @property
    def public_id(self):
        if hasattr(self, '_public_anno') and self._public_anno is not None:
            return self._public_anno.id

    @property
    def public_user(self):
        return 'acct:' + self.h_staging.username + '@hypothesis.is'

    @property
    def text(self):
        return self._text  # XXX short circuit
        reference = f'<p>Public Version: <a href=https://hyp.is/{self.public_id}>{self.public_id}</a></p>'
        if self._anno.user != self.h_curation.username:
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
        if self._anno.user != self.h_curation.username:
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
            if self._anno.user != self.h_curation.username:
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
        # paragraph id= tags
        p = PublicParagraphTags
        
        if self.isAstNode:
            ALERT = f'<p id="{p.Alert}">{self.alert}</p>\n<hr>\n' if self.alert else ''
            curator_notes = ''.join(f'<p id="{p.CuratorNote}">Curator note: {cn}</p>\n' for cn in self.curator_notes)
            curator_note_text = f'{curator_notes}' if self.curator_notes else ''
            curators = ' '.join(f'@{c}' for c in self.curators)
            curator_text = f'<p id="{p.Curators}">Curator: {curators}</p>\n' if self.curators else ''
            resolver_xml_link = f'{self.resolver}{self.rrid}.xml'
            n2t_link = f'http://n2t.net/{self.rrid}'
            idents_link = f'http://identifiers.org/rrid/{self.rrid}'
            links = (f'<p>Resource used:</p>\n'
                     f'<p id="{p.Citation}">\n'
                     f'{self.proper_citation}\n'
                     '</p>\n'
                     f'<p id="{p.Res}">SciCrunch record: <a id="scicrunch.org" href="{self.rridLink}">{self.rrid}</a><p>\n'
                     f'<p id="{p.AltRes}">Alternate resolvers:\n'
                     f'<a id="scicrunch.org" href="{resolver_xml_link}">SciCrunch xml</a>\n'
                     f'<a id="n2t.net" href="{n2t_link}">N2T</a>\n'
                     f'<a id="identifiers.org" href="{idents_link}">identifiers.org</a>\n'
                     '</p>\n') if self.rrid else ''

            _slinks = sorted([self.shareLink] + [r.shareLink for r in self.duplicates])
            slinks = ''.join(f'<a href="{sl}"></a>\n' for sl in _slinks)
            curation_links = (f'<p id="{p.CurLinks}">\n'
                              f'{slinks}'
                              '</p>\n')

            second_hr = '<hr>\n' if curator_text or curator_note_text or links else ''
            return ('<html><body>\n'
                    f'{ALERT}'
                    f'{curator_text}'
                    f'{curator_note_text}'
                    f'{links}'
                    f'{second_hr}'
                    f'<p id="{p.Docs}">\n'
                    f'<a href="{self.docs_link}">What is this?</a>\n'
                    '</p>\n'
                    f'{curation_links}'
                    '</body></html>\n')

    @property
    def tags(self):
        tags = self._fixed_tags
        if self._type == 'reply':  # NOTE replies don't ever get put in public directly
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
        else:
            return [t for t in tags if not t.startswith('RRID:')]  # let self.rrid handle the rrid tags

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
            #if self._anno.user != self.h_curation.username and self.VAL_TAG not in tags:
                #tags.add(self.VAL_TAG)  # we are not going add this tag it is _not_ implied
        return sorted(tags)

    @property
    def public_payload(self):
        if self.isReleaseNode:
            return {
                'uri':self.uri,
                'target':self.target,
                'group':self.h_staging.group,
                'user':self.public_user,
                'permissions':self.h_staging.permissions,
                'tags':self.public_tags,
                'text':self.public_text,
            }

    @property
    def private_payload(self):
        #if self._anno.user != self.h_curation.username:
        payload = {
            'group':self.h_curation.group,
            'permissions':self.h_curation.permissions,
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
        # TODO check with the reply that we leave
        try:
            pa = PublicAnno.getByUriRrid(self.uri, self.rrid)
            return pa
        except (KeyError, ValueError) as e:
            return None

    def post_public(self):
        if READ_ONLY:
            print('WARNING: READ_ONLY is set no action taken')
        else:
            if self._public_anno is None:  # dupes of others may go first
                payload = self.public_payload  # XXX TODO
                if payload:
                    response = self.h_staging.post_annotation(payload)
                    self._public_response = response
                    if response.status_code == 200:
                        anno = HypothesisAnnotation(response.json())
                        pa = PublicAnno.addAnno(anno)
                        return anno, pa
                    else:
                        print(f'Failure to post on {self._python__repr__}')

    def reply_private(self):  # let's keep things immutable
        response = self.h_curation.post_annotation(self.private_payload)
        anno = get_annos.update_annos_from_api_response(response, self.annos)
        return self.__class__(anno, self.annos)

    def patch_curation(self):  # XXX do not use unless you are really sure
        if self.public_id is not None:
            if self._anno.user != self.h_curation.username:
                response = self.h_curation.post_annotation(self.private_payload)
            else:
                response = self.h_curation.patch_annotation(self.id, self.private_payload)
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
rrcu = Curation

def disjoint(*sets):
    return not bool(set.intersection(*(set(s) for s in sets)))

def covering(set_, *covers):
    return set.union(*(set(c) for c in covers)) == set(set_)

def disjointCover(set_, *covers):
    return disjoint(*covers) and covering(set_, *covers)

def sanity_and_stats(rc, annos):
    #papers = rrcu._papers.values()  # this is super slow now?
    rr = [r for r in rc if r.isReleaseNode]
    #with_rrid_good = [r for r in rr if ]

    """  skip for release
    rp = [r for r in rc if r.replies]
    rpt = [r for r in rp if any(re for re in r.replies if re._text)]
    ns = [r for r in rc if r._anno.user != 'scibot']

    # sanity 
    # # all checks
    naa = [r for r in rc if not r.isAstNode and r._type == 'annotation']
    incorrect_with_rrid = [r
                           for r in rc
                           if (r.isReleaseNode and
                               r.INCOR_TAG in r.public_tags and
                               r.rrid)]

    # # release checks
    more_than_one_rrid = [r for r in rr
                          if len([t for t in r.public_tags if 'RRID:' in t]) > 1]
    assert not more_than_one_rrid, f'Annos with more than one RRID {more_than_one_rrid}'
    unvalidated_with_validated_tag = [r for r in rr
                                      if (not [d for d in r.duplicates if d.Validated] and
                                          r.VAL_TAG in r.public_tags and
                                          not r.Validated)]
    # TODO it is probably better to propagate tags through properties and constructing
    # the new tags bunch from that instead of how we do it now? the logic would be clearer
    assert not unvalidated_with_validated_tag, f'HRM unvalidated with val tag... {unvalidated_with_validated_tag}'
    #"""

    # # # covers
    # rrid | no rrid
    # resolved, unresolved | 
    # duplicates, no duplicates
    with_rrid = set(r for r in rr if r.rrid)
    none_rrid = set(r for r in rr if r.rrid is None)

    resolved = set(r for r in with_rrid if r.proper_citation)
    unresolved = set(r for r in with_rrid if not r.proper_citation)

    with_dupes = set(r for r in rr if r.duplicates)
    none_dupes = set(r for r in rr if not r.duplicates)

    with_val = set(r for r in rr if r.Validated)
    none_val = set(r for r in rr if not r.Validated)

    with_cur = set(r for r in rr if r.curators)
    none_cur = set(r for r in rr if not r.curators)

    # # # first release

    none_dupes_resolved = resolved & none_dupes
    fr_best = none_dupes_resolved & with_val
    fr_better = none_dupes_resolved & (with_cur - with_val)
    fr_good = none_dupes_resolved & none_cur
    dj = disjointCover(none_dupes_resolved, fr_best, fr_better, fr_good)
    print('We are disjoint and covering everything we think?', dj)
    first_release = sorted(none_dupes_resolved)


    #testing = sorted(with_val & with_dupes)
    #tests = testing[-10:]
    #tests = sorted(r for r in fr_better if r.corrected)[-10:]
    print('getting public annos')
    pannos = get_pannos()
    if not pannos:
        print('No public annos found.')
        #pannos, pas = zip(*((a, pa) for a, pa in set(r.post_public() for r in tests) if a is not None))
    else:
        print('Found public annos.')
        pas = [PublicAnno(a, pannos) for a in pannos]

    embed()
    return

    # # annoyances

    rrids_with_space = [r for r in with_rrid if ' ' in r.rrid]  # XXX
    #assert not rrids_with_space, f'You have rrids with spaces {rrids_with_space}'
    incor_val = [r for r in rr
                 if allMembers(r.public_tags, r.INCOR_TAG, r.VAL_TAG)]

    no_reply_or_curator = [r for r in rr
                           if (r._anno.user == 'scibot' and
                               r._type == 'annotation' and
                               not (r.replies or r.curators))]

    ur_nrc = set(no_reply_or_curator) & set(unresolved)
    nrc = set(no_reply_or_curator) - set(unresolved)
    assert disjointCover(no_reply_or_curator, ur_nrc, nrc), 'somehow not covering'

    # # unresolved checks
    #ur_val_big = [r for r in unresolved if r.Validated]
    ur_val = [r for r in unresolved if r._Validated]
    ur_cor = [r for r in unresolved if r.corrected]
    ur_rep = [r for r in unresolved if r.replies and not (r.corrected or r.Validated)]  # XXX

    # report gen
    report = report_gen(rrcu.papers.values(), unresolved)
    to_review_txt, to_review_html = to_review(unresolved)

    # specific examples for review
    trouble_children = [
        Curation.byId('89qE6KlKEeeAoyf5DRv2SA'),  # both old and new rrid...
        Curation.byId('KwZFvH4VEeeo4ffGDDoVXA'),  # incor val
        Curation.byId('4EMeDplzEeepi6M5j1gMtw'),
        Curation.byId('zjHIIB83EeehiXsJvha0ow'),  # should include
        Curation.byId('UN4vkAUoEeeUEwvC870_Uw'),  # why is the nested reply not showing???!!?
        #Curation.byId('VE23rgUoEeet9Zetzr9DJA'),  # corrected rrid not overriding
    ]

    # # quality rankings
    best = [r for r in rr if r.rrid and r.proper_citation and r.Validated]
    better = [r for r in rr if r.rrid and r.proper_citation and not r.Validated and r.curators]
    good = [r for r in rr if r.rrid and r.proper_citation and not r.Validated and not r.curators]
    assert set(good) == set(nrc)

    # # corrected
    rr_corrected = [r for r in rr if r.rrid and r.corrected]
    best_corrected = [r for r in best if r.rrid and r.corrected]
    better_corrected = [r for r in better if r.rrid and r.corrected]
    a = set(rr_corrected) - set(best_corrected)
    b = a - set(better_corrected)  # XXX

    best_incor = [r for r in rr if r.rrid is None and r.INCOR_TAG in r.public_tags]
    none_pagenotes = [r for r in rr if r._type == 'pagenote']
    none_annos = [r for r in none_rrid if r._type == 'annotation']
    assert disjointCover(none_rrid, none_pagenotes, none_annos)
    none_not_incor = set(none_annos) - set(best_incor)  # review these

    maybe_covers = (set(best), set(best_corrected), set(better), set(best_incor),
                    set(none_pagenotes), set(none_not_incor))
    maybe_all = covering(set(rr), *maybe_covers)
    if not maybe_all:
        print('Missing', len(rr) - len(set.union(*maybe_covers)), 'annotations')

    me_review = [*rrids_with_space]
    other_review = [*incor_val, *ur_val, *ur_cor]

    print(f'For me:    {len(me_review)}')
    print(f'For other: {len(other_review)}')

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

    print(report)
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

def clean_dupes(get_annos, repr_issues=False):
    annos = get_annos()
    seen = set()
    dupes = [a.id for a in annos if a.id in seen or seen.add(a.id)]
    preunduped = [a for a in annos if a.id in dupes]
    for id_ in dupes:
        print('=====================')
        anns = sorted((a for a in annos if a.id == id_), key=lambda a: a.updated)
        if not repr_issues:
            [print(a.updated, HypothesisHelper(a, annos)) for a in anns]
        for a in anns[:-1]:  # all but latest
            annos.remove(a)
    deduped = [a for a in annos if a.id in dupes]
    assert not len(dupes) or len(preunduped) // len(dupes) == 2, 'Somehow you have managed to get more than 1 duplicate!'
    # get_annos.memoize_annos(annos)
    embed()

def scrapeDoi(url):
    env = os.environ.copy()
    cmd_line = ['timeout', '30s', 'google-chrome-unstable', '--headless', '--dump-dom', url]
    p = subprocess.Popen(cmd_line, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env=env)
    out, err = p.communicate()
    if p.returncode:
        print('UTOH')
        return None
    elif b'ERROR:headless_shell.cc' in out:
        print(out)
        raise IOError('Something is wrong...')
    qurl = quote(url, '')
    if len(qurl) > 200:
        qurl = qurl[:200]
    with open(os.path.expanduser(f'~/files/scibot/{qurl}'), 'wb') as f:
        f.write(out)
    both = BeautifulSoup(out, 'lxml')
    doi = getDoi(both, both)
    return doi

def idPaper(url):
    paper = rrcu._papers[url]
    doi = paper['DOI']
    pmid = paper['PMID']
    print(url)
    if not doi and url.startswith('http'):  # we've go some weird ones in there...
        doi = scrapeDoi(url)
        if doi is not None:
            print(doi)
            try:
                pmid = get_pmid(doi)
            except:  # FIXME stopgap for json weirdness
                print('WARNING json malformed in get_pmid')
                pmid = None
            print(pmid)
            resp = annotate_doi_pmid(url, doi, pmid, rrcu.h_curation, [])
            print('new doi')
            return resp
    else:
        print(doi)
        print('already found')

def review(*objects):
    if len(objects) > 15:
        raise IOError('Trying to review too many ids at once, limit is 15')
    for o in objects:
        os.system('google-chrome-unstable' + o.shareLink)

def ianno(annos):
    n_papers = len(Curation._papers)
    total = [rrid for rrids in Curation._papers.values() for rrid in rrids.keys() if rrid is not None]
    n_total = len(total)
    unique = set(total)
    n_unique = len(unique)

    weird = Curation.byId('AVKzHMeEvTW_3w8LywL_')  # weirdness
    with_replies = [c for c in Curation if c.replies]
    with_curators = [c for c in Curation if c.curators]
    wat = [c for c in Curation if c.curators and not c.replies]
    watnd = [w for w in wat if not w.duplicates]
    #wat = set(with_curators) - (set(Curation) - set(with_replies))  # why didn't this work?
    n_public = len(list(PublicAnno))

    s_t = len([a for a in annos if a.user == 'scibot'])
    ca_t = len([a for a in annos if a.user != 'scibot' and not a.references])
    cr_t = len([a for a in annos if a.user != 'scibot' and a.references])
    n_cur = len(set(a.user for a in annos if a.user != 'scibot'))
    by_cur = defaultdict(list)
    #[by_cur[a.user].append(a) for a in annos]
    for a in annos:
        by_cur[a.user].append(a)
    [print(k, len(v)) for k, v in sorted(by_cur.items(), key=lambda kv:len(kv[1]))]
    c_bins = sorted((len(v) for v in by_cur.values()), reverse=True)[:10]
    import pylab as plt
    plt.bar(range(10), c_bins)
    plt.title('Annotations by user (n = 22)')
    plt.xlabel('Curator rank (top 10)')
    plt.ylabel('Annotations + Replies')
    plt.show()

    dformat = '%Y-%m-%dT%H:%M:%S.%f+00:00'
    def df(s):
        return datetime.strptime(s, dformat)
    time_data = {}
    for id_, paper in Curation._papers.items():
        updateds = []
        s_u = []
        c_u = defaultdict(list)
        for rrid_annos in paper.values():
            for anno in rrid_annos:
                updateds.append(anno.created)
                if anno.user == 'scibot':
                    s_u.append(anno.created)
                else:
                    c_u[anno.user].append(anno.created)
                for reply in anno.replies:
                    updateds.append(reply.created)
                    if anno.user == 'scibot':
                        s_u.append(reply.created)
                    else:
                        c_u[reply.user].append(reply.created)

        all_ = sorted(df(s) for s in updateds)
        s = sorted(df(s) for s in s_u)
        c = {k:sorted(df(s) for s in ss) for k, ss in c_u.items()}
        range_all = all_[0], all_[-1]
        if s:
            range_s = s[0], s[-1]
        else:
            continue
            range_s = None, None  # FIXME
        if c:
            range_c = tuple((max(ss) - min(ss), 0) for ss in c.values())
            #range_c = c[0], c[-1]
        else:
            continue
            range_c = None, None  # FIXME
        time_data[id_] = range_all, range_s, range_c

    delts = {k:tuple((e[1] - e[0]).total_seconds() / 60 if
                     len(e) == 2 and e[0] is not None and e[1] is not None and type(e[0]) != tuple else
                     [e_[0].total_seconds() / 60 for e_ in e] for e in v)
             for k, v in time_data.items()}
    t_bins_base = [e for v in delts.values() for e in v[-1] if e]
    t_bins = [e for e in t_bins_base if e < 30 and e > .5]
    t_big_bins = [e for e in t_bins_base if e >= 30]
    import numpy as np
    plt.hist(t_bins, 30)
    plt.title(f'Curation time < 30 mins (n = {len(t_bins)} $\mu$ = {np.average(t_bins):.2f} med = {np.median(t_bins):.2f})')
    plt.xlabel('Time (minutes)')
    plt.ylabel('Number of curation sessions duration less than x')
    plt.show()
    plt.hist(t_big_bins, 20)
    plt.title(f'Curation time > 30 mins (n = {len(t_big_bins)})')
    plt.xlabel('Time (minutes)')
    plt.ylabel('Number of curation sessions duration less than x')
    plt.show()

def main():
    from desc.prof import profile_me

    # clean updated annos
    #clean_dupes(get_annos, repr_issues=True)
    #return

    # fetching
    annos = get_annos()
    #_annos = annos
    #annos = [a for a in annos if a.updated > '2017-10-15']

    # loading
    #@profile_me
    #def load():
        #for a in annos:
            #rrcu(a, annos)
    #load()
    #rc = list(rrcu.objects.values())
    rc = [rrcu(a, annos) for a in annos]

    # id all the things
    #from joblib import Parallel, delayed
    #id_annos = []
    #for purl in rrcu._papers:
        #resp = idPaper(purl)
        #id_annos.append(resp)
    #id_annos = Parallel(n_jobs=5)(delayed(idPaper)(url)
                                  #for url in sorted(rrcu._papers))
    #embed()
    #return

    # sanity checks
    #print('repr everything')
    #_ = [repr(r) for r in rc]  # exorcise the spirits  (this is the slow bit, joblib breaks...)
    try:
        stats = sanity_and_stats(rc, annos)
        ianno_stats = ianno(annos)
    except AssertionError as e:
        print(e)
        embed()

if __name__ == '__main__':
    main()

