
from pyontutils.utils import noneMembers, anyMembers
from hyputils.hypothesis import HypothesisUtils, HypothesisAnnotation, HypothesisHelper, Memoizer
from export import api_token, username, group, group_public, bad_tags

get_annos = Memoizer(api_token, username, group, memoization_file='/tmp/real-scibot-annotations.pickle')

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
    REPLY_TAG = 'RRIDCUR:Released-Parent'
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
    known_bad = ['M6oR1Lj5EeeP65teqMF8RA',
                 'nYbrLLW7EeeQ4wPyyu7iqw',
                 'UPhsBq-DEeegjsdK6CuueQ',
                 'UI4WWK95Eeea6a_iF0jHWg',
                 'HdNDhK93Eeem7sciBew4cw',
                 'TwobZK91Eee7P1c_azGIHA',
                 'ZdtjrK91EeeaLwfGBVmqcQ',
                 'KU1eDKh-EeeX9HMjEOC6rA',
                 'uvwscqheEeef8nsbQydcag',
                 '09rXMqVKEeeAuCfc1MOdeA',
                 'nBsIdqSHEee2Zr-s9njlHA',
                ]

    def _fetch_xml(self):
        resp = requests.get(self.resolver + self.rrid + '.xml')
        self._xml = resp.content  # TODO 404 check

    @property
    def uri(self): return self._anno.uri

    @property
    def target(self): return self._anno.target

    @property
    def alert(self):
        if self.INCOR_TAG in self.tags:
            return 'No record found.'  # if there is not a replacement RRID listed along with this tag then alert that we could find no RRID at all for this
        elif self.CORR_TAG in self.tags:
            return 'Identifier corrected.'
        else:
            return None

    @property
    def rrid(self):  # FIXME
        # cannot call self.tags from here
        # example of case where I need to check for RRIDCUR:Incorrect to make the right determination
        "-3zMMjc7EeeTBfeviH2gHg"
        #https://hyp.is/-3zMMjc7EeeTBfeviH2gHg/www.sciencedirect.com/science/article/pii/S0896627317303069

        maybe = [t for t in self._tags if t not in self.skip_tags and 'RRID:' in t]
        if maybe:
            if len(maybe) > 1:
                if self.id not in self.known_bad:
                    raise ValueError(f'More than one rrid in {maybe} \'{self.id}\' {self.shareLink}')
            rrid = maybe[0]
        elif self._type == 'reply' and self._text.startswith('RRID:'):
            # special case for the old practice of putting the correct rrid in the text instead of the tags
            rrid = self._text.strip()
        else:
            rrid = None

        if self._type == 'reply':
            return rrid
        elif self._type == 'annotation':
            reps = [r for r in self.replies if r.rrid]
            if reps:
                if len(reps) > 1:
                    if len(set(r.rrid for r in reps)) == 1:
                        print(f'WARNING multiple replies with the same rrid in {reps}')
                    else:
                        raise ValueError(f'More than one rrid in {reps}')
                rep = reps[0]
                if self.CORR_TAG in rep.tags:
                    return rep.rrid
                elif self.INCOR_TAG in rep.tags:
                    return None
            return rrid

    @property
    def isAstNode(self):
        if self._type == 'annotation' and noneMembers(self._tags, *self.skip_anno_tags):
            return True
        else:
            return False

    @property
    def proper_citation(self):
        if self.isAstNode:
            if not hasattr(self, '_xml'):
                return 'XML was not fetched no citation included.'
                self._fetch_xml()
            pc = get_proper_citation(self._xml)
            if not pc.startswith('('):
                pc = f'({pc})'
            return pc

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
    def text(self):
        reference = f'<p>Public Version: <a href=https://hyp.is/{self.public_id}>{self.public_id}</a></p>'
        if self._anno.user != self.h_private.username:
            return reference
        else:
            return reference + self._text

    @property
    def public_text(self):
        if self.isAstNode:

            ALERT = '<p>{self.alert}</p>\n<hr>' if self.alert else ''
            curator_text = f'<p>Curator: {self._anno.user}</p>\n' if self._anno.user != self.h_private.username else ''
            curator_note_text = f'<p>Curator note: {self._text}</p>\n' if self._anno.user != self.h_private.username and self._text else ''
            resolver_link = f'{self.resolver}{self.rrid}'
            resolver_xml_link = f'{self.resolver}{self.rrid}.xml'
            nt2_link = f'http://nt2.net/{self.rrid}'
            idents_link = f'http://identifiers.org/{self.rrid}'
            links = (f'<p>Resource used:<br>\n{self.proper_citation}\n</p>\n'
                     f'<p>SciCrunch record: <a href={resolver_link}>{self.rrid}</a><p>\n'
                     '<p>Alternate resolvers:<br>\n'
                     f'<a href={resolver_xml_link}>SciCrunch xml</a>\n'
                     f'<a href={nt2_link}>N2T</a>\n'
                     f'<a href={idents_link}>identifiers.org</a>'
                     '</p>') if self.rrid else ''

            return (f'{ALERT}'
                    f'Resource used\n'
                    f'{curator_text}'
                    f'{curator_note_text}'
                    f'{links}'
                    '<hr>'
                    f'<p><a href={self.docs_link}>What is this?</a></p>')

    @property
    def tags(self):
        if self.isAstNode:
            if self._anno.user != self.h_private.username:
                return [self.REPLY_TAG]
            else:
                return sorted(self._tags + [self.SUCCESS_TAG])
        elif self._type == 'reply':
            tags = []
            for tag in self._tags:
                if tag.startswith('RRID:'):
                    continue  # we deal with the RRID itself in def rrid(self)  # NOTE replies don't ever get put in public directly...
                elif tag == self.INCOR_TAG and self.rrid:
                    tags.append(self.CORR_TAG)
                else:
                    tags.append(tag)
            return sorted(tags)


    @property
    def public_tags(self):
        if self._anno.user != self.h_private.username:
            if self.rrid:
                return [self.rrid, self.VAL_TAG]  # FIXME this isn't right
        else:
            tags = []
            for reply in self.replies:
                for tag in reply.tags:
                    if tag not in self.skip_tags:
                        tags.append(tag)
                for tag in self._tags:
                    if not tag.startswith('RRID:'):
                        tags.append(tag)
                    if self.CORR_TAG in tags and tag == self.INCOR_TAG:
                        continue
                    #if anyMember(tags, self.CORR_TAG, self.INCOR_TAG) and tag.startswith('RRID:'):
                        #continue  # if we corrected the RRID or it was wrong do not include it as a tag
                if self.rrid:
                    tags.append(self.rrid)
            return sorted(tags)

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
            response = self.h_public.post_annotation(payload)
            self._public_response = response
            self._public_anno = HypothesisAnnotation(response.json())
            self.public_annos[self._public_anno.id] = self._public_anno

    def patch_private(self):
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
        rrid_text =  f'\n{t}rrid:         {self.rrid}' if self.rrid else ''
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
                f'{uri_text}'
                f'{doi_text}'
                f'{pmid_text}'
                f'{rrid_text}'
                f'{exact_text}'
                f'{_text_text}'
                f'{text_text}'
                f'{_tag_text}'
                f'{tag_text}'
                f'{ptext}'
                f'{ptag_text}'
                f'{replies_text}'
                f'\n{t}____________________')

def main():
    from IPython import embed
    from desc.prof import profile_me
    annos = get_annos()
    @profile_me
    def load():
        for a in annos:
            RRIDCuration(a, annos)
    load()
    rc = list(RRIDCuration.objects.values())
    rp = [r for r in rc if r.replies]
    rpt = [r for r in rp if any(re for re in r.replies if re._text)]
    ns = [r for r in rc if r._anno.user != 'scibot']
    _ = [repr(r) for r in rc]  # exorcise the spirits
    embed()

if __name__ == '__main__':
    main()

