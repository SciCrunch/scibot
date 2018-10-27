from collections import defaultdict
from pathlib import Path
from rdflib import URIRef
from IPython import embed
from pyontutils.core import makeGraph, OntId, OntCuries
import pyontutils.graphml_to_ttl as gt
from pyontutils import combinators as cmb
from pyontutils.utils import working_dir, TermColors as tc
from pyontutils.graphml_to_ttl import workflow as wf, RRIDCUR
from pyontutils.closed_namespaces import rdf, rdfs, owl
from itertools import chain
from rdflib import ConjunctiveGraph, BNode
from hyputils.hypothesis import Memoizer, HypothesisHelper
from scibot.utils import uri_normalization
#from rdflib.extras import infixowl as io

from pyontutils.graphml_to_ttl import WorkflowMapping, PaperIdMapping

curator_exactrrid_unrecognized_rrid = None
curator_exactrrid_syntax_error_rrid = None
curator_exactrrid_incorrect_rrid = None

curator_exactmeta_missing_future = None
curator_exactmeta_missing_rrid = None

scibot_exact_rrid_incorrect = None
scibot_exact_rrid_validated = None
scibot_exact_rrid_metadata_mismatch = None

scibot_exact_unresolved_incorrect = None
scibot_exact_unresolved_insufficient_metadata = None
scibot_exact_unresolved_not_rrid_wtf = None
scibot_exact_unresolved_not_rrid_duplicate = None
scibot_exact_unresolved_not_rrid_rrid = None
scibot_exact_unresolved_not_rrid_insufficient_metadata = None


class Workflow:

    def __init__(self, anno):
        pass

    def release(self):
        return False

    def not_done(self):
        return self.current_step

    def annotation(self):
        pass

    def reply(self):
        pass

    @property
    def scibot(self):
        return self.user == self.robot_user
    @property
    def curator(self):
        return not self.scibot

    @property
    def scibot_exact(self):
        if self.scibot:
            return self.anno.exact
    @property
    def scibot_rrid(self):
        if self.scibot:
            return next(t for t in self.scibot_tags if t.startswith('RRID:'))

    @property
    def scibot_unresolved(self):
        if self.scibot:
            return 'RRIDCUR:Unresolved' in self.tags

    # either zip up 

    @property
    def curator_exact(self):
        if self.curator and self.annotation:
            return self.anno.exact

    @property
    def curator_exact_meta(self):
        # we are detecting this in reverse it is not a causal input
        if self.curator_missing:
            return self.curator_exact

    @property
    def curator_exact_rrid(self):
        if self.curator and self.annotation and not self.curator_exact_meta:
            return self.curator_exact

    @property
    def curator_rrid(self):
        if self.curator:
            multiple_rrids = False
            for tag in self.curator_tags:
                if tag.startswith('RRID:'):
                    if multiple_rrids:
                        raise
                    yield tag
                    trap = True

    @property
    def curator_tags(self):
        if self.curator:
            return self.tags
        else:
            for reply in self.tc_replies:
                # TODO proper ordering
                # TODO bad tag patterns
                yield from reply.tags
            
    def curator_tag(self, tag):
        if self.curator:
            return tag in self.curator_tags

    @property
    def curator_validated(self):
        return self.curator_tag('RRIDCUR:Validated')
    @property
    def curator_incorrect(self):
        return self.curator_tag('RRIDCUR:Incorrect')
    @property
    def curator_insufficient_metadata(self):
        return self.curator_tag('RRIDCUR:InsufficientMetadata')
    @property
    def curator_not_rrid(self):
        return self.curator_tag('RRIDCUR:NotRRID')

    @property
    def curator_unrecognized(self):
        return self.curator_tag('RRIDCUR:Unrecognized')
    @property
    def curator_syntax_error(self):
        return self.curator_tag('RRIDCUR:SyntaxError')
    @property
    def curator_missing(self):
        return self.curator_tag('RRIDCUR:Missing')


def test():
    class Anno:
        def __init__(self, user, exact, tags):
            pass

    annos = [
        Anno(self.robot_user, 'AB_000000', ['RRID:AB_000000']),
        Anno(self.robot_user, 'AB_000001', ['RRIDCUR:Unresolved']),
        Anno('tgbugs', 'metadata', ['RRIDCUR:Missing', 'RRID:AB_123456']),
    ]

    w = [Workflow(a) for a in annos]


class DashboardState:
    def __init__(self, states):
        pass

    def add_anno(self, anno):
        pass


class AtomicAnno:
    _cache = {}
    def __init__(self, anno_id, tags, user, references, exact=None, document=None):  # FIXME need exact/no exact for anno vs pagenote?
        # document comes from the db which would already have
        # accounted for our "more" normalized forms ...
        self.id = anno_id
        self.tags = tags
        self.user = user
        self.all_tags = []
        # this is super annoying because people edit things :/
        # which means that we have to propagate on all chains
        for reference in references:
            if reference not in self._cache:
                self.all_tags
        self.state_tags = []

        self._cache[id] = self


class Document:
    def __init__(self, normalized_uris, uris, doi, pmid):
        pass


class AnnoAsTags:
    """ WARNING this class is a disaster zone. """
    robot_user = 'scibot'
    tag_prefix = 'RRIDCUR'
    info_tags = frozenset(('RRIDCUR:Duplicate', 'RRIDCUR:Misplaced'))
    # TODO auto smart propagate? when a new correction is added?
    cv_tags = {'RRIDCUR:NoPaperID':'RRIDCUR:NoPaperId',
               'RRIDCUR:InsufficientMetaData':'RRIDCUR:InsufficientMetadata',
               'RRIDCUR:MetadataMistmatch':'RRIDCUR:MetadataMismatch',  # FIXME SPELLING
               'RRIDCUR:noPMID':'RRIDCUR:NoPMID',
    }
    # RRIDCUR:Duplicate is an information -> curator only tag and can't be trusted
    tag_types = tuple()
    anno_part_instances = tuple()  # dict
    tag_transitions = tuple()  # dict
    valid_tagsets = tuple()
    terminal_tagsets = tuple()  # dict
    annos = tuple()  # FIXME database database
    annos_dict = tuple()  # FIXME DBDB
    warnings = frozenset()  # shared empty
    aat_dict = {}
    _tag_cache = {}
    _setup_done = False
    # TODO factoryify

    def __new__(cls, *args, **kwargs):
        if not cls._setup_done:
            cls.infotags = frozenset((OntId(t) for t in cls.info_tags))  # just to make it even more confusing
            cls.cvtags = {OntId(cvt):OntId(t) for cvt, t in cls.cv_tags.items()}  # just to make it even more confusing
            for tag in set(t for s in chain(cls.terminal_tagsets, (cls.infotags,)) for t in s):
                if tag.prefix == cls.tag_prefix:
                    @property
                    def getter(self, t=tag):
                        return t in set(self.tagset) or t in set(self.badset)

                    setattr(cls, tag.suffix, getter)

            cls._setup_done = True

        return object.__new__(cls)

    def __init__(self, anno):
        self.anno = anno
        self.uri = anno.uri
        self.uri_normalized = uri_normalization(self.uri)
        self.id = anno.id
        self.aat_dict[self.id] = self
        self.user = anno.user
        self.orphaned = False  # will be set when looking for parents FIXME orphaned is transitive

        exacts = []  # because some implementations allow more than one
        for target in self.raw['target']:
            if 'selector' in target:
                for selector in target['selector']:
                    if 'exact' in selector:
                        exacts.append(selector['exact'])

        self.isReply = bool(anno.references)
        self.isPageNote = not bool(exacts)
        self.isAnnotation = not self.isReply and not self.isPageNote

        self.exacts = exacts

        try:
            self.tagset = frozenset(self.all_tags)
            # FIXME squashes multiple RRIDs
            # this tells us that it is minimally consistent
            # but we requrie more checks
            #self.tagset = frozenset(OntId(t) if t else t
                                    #for t in self.all_tags)
        except KeyError as e:
            raise ValueError(f'{list(self.all_tags)}') from e

        self.badset = frozenset(self.all_bads)

        self.DOIs = set(t for t in self.ontid_all_tags if t and t.prefix == 'DOI')
        self.PMIDs = set(t for t in self.ontid_all_tags if t and t.prefix == 'PMID')
        self.RRIDscibot = set(t for t in self.scibot_root_tags if t and t.prefix == 'RRID')
        self.RRIDscibotCanonical = set(t for t in self.scibot_reply_tags if t and t.prefix == 'RRID')
        self.RRIDcurator = set(t for t in self.curator_tags if t and t.prefix == 'RRID')

    @property
    def putativeRRID(self):
        if self.user == self.robot_user and self.isAnnotation:
            return self.exacts[0]  # putatives could break OntId, so keep as string
        elif self.user != self.robot_user and (not self.RRIDscibot or self.Unresolved):
            for parent in self.parents:
                return parent.putativeRRID

    @classmethod
    def byId(cls, aid):
        return cls.aat_dict[aid]

    @property
    def raw(self):
        return self.anno._row

    def _getAATById(self, aid):
        return self.aat_dict[aid]

    @property
    def parents(self):
        if not self.orphaned:
            for aid in self.anno.references:
                try:
                    yield self._getAATById(aid)
                except KeyError:
                    self.orphaned = True
                    print(tc.red('WARNING:'), f'parent annotation was deleted from {self.id}')

    @property
    def tags(self):
        yield from self.anno.tags

    @property
    def ontid_all_tags(self):
        for t in chain(self.tags, (t for p in self.parents for t in p.tags)):
            tag = self._tag_cache[t]
            if tag:
                yield tag

    @property
    def all_tags(self):
        yield from (t for a in chain(self.parents, (self,))
                    for t in a.subbed_tags)

    @property
    def curator_tags(self):
        yield from (self._tag_cache[t]  # this should always succeed ...
                    for a in chain(self.parents, (self,))
                    if a.user != self.robot_user
                    for t in a.tags)

    @property
    def scibot_root_tags(self):
        """ annotation or page note """
        yield from (self._tag_cache[t]  # this should always succeed ...
                    for a in chain(self.parents, (self,))
                    if a.user == self.robot_user and not self.isReply
                    for t in a.tags)

    @property
    def scibot_reply_tags(self):
        yield from (self._tag_cache[t]  # this should always succeed ...
                    for a in chain(self.parents, (self,))
                    if a.user == self.robot_user and self.isReply
                    for t in a.tags)

    @property
    def scibot_tags(self):
        yield from self.scibot_root_tags
        yield from self.scibot_reply_tags

    @property
    def all_bads(self):
        # FIXME this chain propagates behind fixes >_<
        # FIXME this is extremely dangerous code duplication
        # that will break logic because it allows propagation
        # of an 'unfixed' view of the parent tags
        # the correct solution is static binning of all tags
        # during init and decoupling the state detection from
        # the actual tags >_<
        for anno in self.parents:
            for t in anno.badtags:
                if t not in self.info_tags:
                    yield t

        yield from self.badtags

    @property
    def subbed_tags(self):
        for tag in self.tags:
            yield self.tagsub(tag)

    @property
    def badtags(self):
        for tag in self.anno.tags:
            if self.tagsub(tag) is None:
                yield tag

    def _tagsub_wrap(self, tag):
        """ doesn't do what we want """
        try:
            return self._tag_cache[tag]
        except KeyError:
            subbed = self._tagsub(tag)
            self._tag_cache[tag] = subbed
            return subbed

    def tagsub(self, tag):
        try:
            if tag in self._tag_cache:
                tag = self._tag_cache[tag]
                if tag is None:
                    return tag
            else:
                subbed = OntId(tag)
                self._tag_cache[tag] = subbed
                tag = subbed
        except (OntId.BadCurieError, OntId.UnknownPrefixError) as e:
            self._tag_cache[tag] = None
            return None

        if tag.prefix == 'RRID':
            if self.user == self.robot_user:
                return OntId('workflow:RRIDscibot')
            else:
                # TODO suffix check?
                return OntId('workflow:RRID')
        elif tag.prefix == 'DOI':
            return OntId('workflow:DOI')
        elif tag.prefix == 'PMID':
            return OntId('workflow:PMID')
        elif tag.prefix == 'RRIDCUR':
            api = self.anno_part_instances
            if self.user == self.robot_user and tag not in api[OntId('workflow:tagScibot')]:
                return None  # return None to gurantee invalid tagset w/o errors
            elif self.user != self.robot_user and tag not in api[OntId('workflow:tagCurator')]:
                return None
            else:
                return tag
        else:
            return None

    def exact(self):
        pass

    def pageNote(self):
        pass

    def __repr__(self):
        _tagset = ' '.join(sorted(t.curie if t is not None else 'None' for t in self.tagset))
        tagset = '(' + _tagset + ')' if _tagset else '()'
        _badset = ' '.join(sorted(t for t in self.badset))
        badset = ' (' + _badset + ')' if _badset else ' ()'
        _ontid_all_tags = ' '.join(sorted(t.curie for t in self.ontid_all_tags))
        ontid_all_tags = ' (' + _ontid_all_tags + ')' if _ontid_all_tags else ' ()'

        return f'{self.__class__.__name__}.byId({self.id!r})  # {tagset}{badset}{ontid_all_tags}'


class TagLogic(AnnoAsTags):
    aat_dict = {}
    def __init__(self, anno):
        super().__init__(anno)
        self.validate()
        self.invalid = bool(self.reason_invalid)
        self.valid = not self.invalid

    def special_case(self):  # FIXME wow is this bad
        # handle info_tags
        badset = set(OntId(t) if t.startswith('RRIDCUR:')
                     and ' ' not in t  # *shakes fist angrily*
                     else t
                     for t in self.badset)


        tagset = frozenset(badset | self.tagset - {None})
        for itag in self.infotags:
            if itag in tagset:
                tagset = frozenset((t for t in tagset if t != itag))
                self.warnings |= frozenset({itag})

        for cv_tag, tag in self.cvtags.items():
            if cv_tag in tagset:
                tagset = tagset - frozenset((cv_tag))
                tagset |= frozenset((tag))
                self.warnings |= frozenset({cv_tag})


        def rrid_safe_suffix(_):
            hah = next(iter(self.RRIDcurator))  # FIXME multicase ...
            return not hah.suffix in set(t.suffix
                                         for t in self.anno_part_instances[OntId('workflow:tagCurator')])

        scs = {
            # TODO make sure that ONLY the workflow tags are used to retrieve values
            # so that annotations with an RRID: tag that are/were unresolved have to
            # to into a special handline pipeline FIXME this implementation is NOT sufficient
            ('workflow:RRID',):
            (rrid_safe_suffix, ('workflow:RRID', 'RRIDCUR:Missing')),
            ('workflow:RRID', 'RRIDCUR:Validated'):
            (lambda x:True, ('RRIDCUR:Validated',)),  # rrid deal with elsewhere
            ('workflow:RRID', 'RRIDCUR:Unresolved'):  # super confusing ...
            (lambda x:True, ('RRIDCUR:GiveMeAReason',)),
            ('workflow:RRIDscibot', 'RRIDCUR:Unresolved'):
            (lambda x:True, ('RRIDCUR:Unresolved',)),
            #('workflow:RRID',): ('workflow:RRID', 'RRIDCUR:Missing'),
            # can't use this yet due to the bad RRID:Missing and friends issues
            #('',): ('',),
        }
        special_cases = {}
        for special, (test, case) in scs.items():
            special_cases[
                frozenset((OntId(s) for s in special))
            ] = test, frozenset((OntId(c) for c in case))

        if tagset in special_cases:
            test, new_tagset = special_cases[tagset]
            if test(tagset):
                self.warnings |= tagset
                return new_tagset
            else:
                return None
        elif self.warnings:  # itags
            return tagset

    def validate(self):
        """ validate a single reply chain """
        self.reason_invalid = tuple()
        if self.badset:
            badset = self.badset - self.info_tags - frozenset(self.cv_tags)  # FIXME make this accessible
            if badset:
                self.reason_invalid += ('There are bad tags.',)

        if self.tagset not in self.valid_tagsets:
            special_case = self.special_case()  # TODO do something with special case?
            if not special_case:
                self.reason_invalid += ('Invalid tagset',)  # TODO post possible fixes

        if self.orphaned:
            self.reason_invalid += ('Orphaned',)

        # the tests below usually will not trigger at this stage
        # because the issue usually arrises only when looking across multiple
        # reply threads, thus what we need to do is flag any reply chains that
        # have been superseeded

        if len(self.DOIs) > 1:
            self.reason_invalid += ('Too many DOIs',)

        if len(self.PMIDs) > 1:
            self.reason_invalid += ('Too many PMIDs',)

        if len(self.RRIDcurator) > 1:
            self.reason_invalid += ('Too many curator RRIDs',)

        if len(self.RRIDscibot) > 1:  # only the paranoid survive
            self.reason_invalid += ('Too many scibot RRIDs',)

        if self.Unresolved and len(self.RRIDcurator) == 1:
            curatorRRID = next(iter(self.RRIDcurator))
            if curatorRRID.curie == self.putativeRRID:  # putatives could break OntId, so keep as string
                self.reason_invalid += ('Unresolved scibot RRID matches curator RRID',)

    @property
    def next_tags(self):
        if self.valid:
            for next_state in self.tag_transitions[self.tagset]:
                yield from next_state - self.tagset

    @property
    def current_state(self):
        if self.invalid:  # modelViolated
            return 'TEMP:needsQC'
        else:
            return 'TODO'
        
    @property
    def initiatesAction(self):
        # compute wheter an action needs to be taken based on the state we are in
        # NOTE this is orthogonal to terminals and endpoints
        # hrm ... PDA ... HRM
        if self.tagset in self.terminal_tagsets:
            return self.terminal_tagsets[self.tagset]
        else:
            # TODO ar there states that require something elseseomthin?
            pass


def write(graph, path, format='nifttl'):
    with open(path, 'wb') as f:
        f.write(graph.serialize(format=format))


def parse_workflow():
    # FIXME TODO these states should probably be compiled down to numbers???
    docs = Path(__file__).parent.absolute().resolve().parent / 'docs'
    rridpath = docs / 'workflow-rrid.graphml'
    paperpath = docs / 'workflow-paper-id.graphml'

    cgraph = ConjunctiveGraph()
    gt.WorkflowMapping(rridpath.as_posix()).graph(cgraph)
    gt.PaperIdMapping(paperpath.as_posix(), False).graph(cgraph)
    write(cgraph, '/tmp/workflow.ttl')
    predicates = set(cgraph.predicates())
    OntCuries({cp:str(ip) for cp, ip in cgraph.namespaces()})
    OntCuries({'RRID': 'https://scicrunch.org/resolver/RRID:',
               'DOI': 'https://doi.org/',
               'PMID': 'https://www.ncbi.nlm.nih.gov/pubmed/'})
    hg = makeGraph('', graph=cgraph)
    short = sorted(hg.qname(_) for _ in predicates)

    wf.hasTag
    wf.hasReplyTag
    wf.hasTagOrReplyTag
    wf.hasOutputTag

    #if type isa wf.tag

    tag_types = set(cgraph.transitive_subjects(rdfs.subClassOf, wf.tag))
    tag_tokens = {tagType:sorted(set(t for t in cgraph.transitive_subjects(rdf.type, tagType)
                                     if t != tagType))
                  for tagType in tag_types}
    has_tag_types = set(cgraph.transitive_subjects(rdfs.subPropertyOf, wf.hasTagOrReplyTag))
    has_tag_types.add(wf.hasOutputTag)
    has_next_action_types = set(cgraph.transitive_subjects(rdfs.subPropertyOf, wf.hasOutput))
    has_next_action_types.add(wf.hasNextStep)

    terminals = sorted(tag
                       for ttype in tag_types
                       if ttype != wf.tagScibot  # scibot is not 'terminal' for this part
                       for tag in cgraph[:rdf.type:ttype]
                       if not isinstance(tag, BNode)
                       and not any(o for httype in has_tag_types
                                   for o in cgraph[tag:httype]))

    endpoints = sorted(endpoint
                       for endpoint in cgraph[:rdf.type:wf.state]
                       if not isinstance(endpoint, BNode)
                       and not any(o for hnatype in has_next_action_types
                                   for o in cgraph[endpoint:hnatype]))

    complicated = sorted(a_given_tag
                 for tt in tag_types
                 for a_given_tag in cgraph[:rdf.type:tt]
                 if not isinstance(a_given_tag, BNode)
                         and not [successor_tag
                          for htt in has_tag_types
                          for successor_tag in chain(t
                                                     for t in cgraph[a_given_tag:htt]
                                                     #if not isinstance(t, BNode)
                                        ,
                                                     # we don't actually need this for terminals
                                                     # we will need it later
                                                     #(t for b in cgraph[a_given_tag:htt]
                                                     #if isinstance(b, BNode)
                                                     #for listhead in cgraph[b:owl.oneOf]
                                                     #for t in unlist(listhead, cgraph)),
                         )])

    def topList(node, g):
        for s in g[:rdf.rest:node]:
            yield s

    def getLists(node, g):
        for linker in g[:rdf.first:node]:
            top = None
            for top in g.transitiveClosure(topList, linker):
                pass

            if top:
                yield top
            else:
                yield linker

    def getIsTagOf(node, g):
        for htt in has_tag_types:
            for parent_tag in g[:htt:node]:
                yield parent_tag

    def getIsOneOfTagOf(node, g):
        for list_top in getLists(node, g):
            for linker in g[:owl.oneOf:list_top]:
                for parent_tag, _ in g[::linker]:
                    yield parent_tag

    def getPreviousTag(node, g):  # not quite what we need
        yield from getIsOneOfTagOf(node, g)
        yield from getIsTagOf(node, g)

    def getTagChains(node, g, seen=tuple()):
        # seen to prevent recursion cases where
        # taggning can occur in either order e.g. PMID -> DOI
        #print(tc.red(repr(OntId(node))))  # tc.red(OntId(node)) does weird stuff O_o
        parent_tag = None
        for parent_tag in chain(getIsOneOfTagOf(node, g),
                                getIsTagOf(node, g)):
            if parent_tag in seen:
                parent_tag = None
                continue
            ptt = next(g[parent_tag:rdf.type])
            #if ptt in tag_types:
            for pchain in getTagChains(parent_tag, g, seen + (node,)):
                if ptt in tag_types:
                    out = parent_tag, *pchain
                else:
                    out = pchain
                yield out

            if not ptt and not out:
                parent_tag = None

        if not parent_tag:
            yield tuple()

    def getInitiatesAction(node, g):
        for action in g[:wf.initiatesAction:node]:
            yield action

    def getIsOneOfOutputOf(node, g):
        for list_top in getLists(node, g):
            for linker in g[:owl.oneOf:list_top]:
                for hot in has_next_action_types:
                    for parent_thing  in g[:hot:linker]:
                        yield parent_thing

    def getActionChains(node, g):
        parent_action = None
        for parent_action in chain(getIsOneOfOutputOf(node, g),  # works for actions too
                                   getInitiatesAction(node, g)):
            for pchain in getActionChains(parent_action, g):  # NOTE may also be a tag...
                out = parent_action, *pchain
                #print(tuple(hg.qname(o) for o in out))
                yield out

        if not parent_action:
            yield tuple()

    def getRestSubjects(predicate, object, g):
        """ invert restriction """
        rsco = cmb.Restriction(rdfs.subClassOf)
        for rt in rsco.parse(graph=g):
            if rt.p == predicate and rt.o == object:
                yield from g.transitive_subjects(rdfs.subClassOf, rt.s)

    annoParts = list(getRestSubjects(wf.isAttachedTo, wf.annotation, cgraph))
    partInstances = {OntId(a):set(t if isinstance(t, BNode) else OntId(t)
                                  for t in cgraph.transitive_subjects(rdf.type, a)
                                  if not isinstance(t, BNode) and t != a)
                     for a in annoParts}

    _endpoint_chains = {OntId(endpoint):[[OntId(endpoint)] + [OntId(e) for e in chain]
                                            for chain in getActionChains(endpoint, cgraph)]
                        for endpoint in endpoints}

    #print([hg.qname(e) for e in endpoints])
    #print([print([hg.qname(c) for c in getActionChains(endpoint, cgraph) if c])
           #for endpoint in endpoints
           #if endpoint])

    #_ = [print(list(getActionChains(e, cgraph)) for e in endpoints)]
    #return

    wat = cgraph.transitiveClosure(getPreviousTag, RRIDCUR.Duplicate)
    wat = list(wat)
    #def invOneOf(tag, g):

    fake_chains = {hg.qname(terminal):
                   [hg.qname(c)
                    for c in cgraph.transitiveClosure(getPreviousTag, terminal)]
                   for terminal in terminals}

    def make_chains(things, getChains):
        return {OntId(thing):[[OntId(thing)] + [OntId(e) for e in chain]
                              for chain in getChains(thing, cgraph)]
                for thing in things
                #if not print(thing)
        }

    def print_chains(thing_chains):
        print('\nstart from beginning')

        print('\n'.join(sorted(' -> '.join(hg.qname(e) for e in reversed(chain))
                               for chains in thing_chains.values()
                               for chain in chains)))

        print('\nstart from end')

        print('\n'.join(sorted(' <- '.join(e.curie for e in chain)
                               for chains in thing_chains.values()
                               for chain in chains)))

    def valid_tagsets(all_chains):
        # not the most efficient way to do this ...
        transitions = defaultdict(set)
        for end, chains in all_chains.items():
            for chain in chains:
                valid = set()
                prior_state = None
                for element in reversed(chain):
                    valid.add(element)
                    state = frozenset(valid)
                    transitions[prior_state].add(state)
                    prior_state = state

        return {s:frozenset(n) for s, n in transitions.items()}

    endpoint_chains = make_chains(endpoints, getActionChains)
    #endpoint_transitions = valid_transitions(endpoint_chains)  # not the right structure
    print_chains(endpoint_chains)
    terminal_chains = make_chains(terminals, getTagChains)
    print_chains(terminal_chains)
    tag_transitions = valid_tagsets(terminal_chains)
    terminal_tags_to_endpoints =  'TODO'

    def printq(*things):
        print(*(OntId(t).curie for t in things))

    from pprint import pprint
    def get_linkers(s, o, g, linkerFunc):  # FIXME not right
        for p in g[s::o]:
            yield p

        for l in linkerFunc(o, g):
            #print(tc.blue(f'{OntId(s).curie} {l if isinstance(l, BNode) else OntId(l).curie}'))
            for p in g[s::l]:
                #print(tc.red(f'{s} {l} {o} {p}'))
                yield p
        return 
        linkers = set(l for l in g.transitiveClosure(linkerFunc, o))
        for p, o in g[s::]:
            if o in linkers:
                yield p

    def edge_to_symbol(p, rev=False):
        if p == wf.initiatesAction:
            return '<<' if rev else '>>'
        elif p == wf.hasReplyTag:
            return '<' if rev else '>'
        elif p == wf.hasTagOrReplyTag:
            return '<=' if rev else '=>'
        elif p == wf.hasOutputTag:
            return '-<-' if rev else '->-'
        else:
            return '<??' if rev else '??>'

    def chain_to_typed_chain(chain, g, func):
        # duh...
        #pprint(chain)
        for s, o in zip(chain, chain[1:]):
            # TODO deal with reversed case
            s, o = s.u, o.u
            p = None
            #print(s, o)
            printq(s, o)
            for p in get_linkers(s, o, g, func):
                #print(tc.yellow(p))
                #yield (s, edge_to_symbol(p), o)
                yield from (s, edge_to_symbol(p), o)

            if not p:
                for rp in get_linkers(o, s, g, func):
                    print(tc.blue(rp))
                    yield from (s, edge_to_symbol(rp, rev=True), o)

    def tchains(thing_chains, func):
        return sorted([OntId(e).curie if isinstance(e, URIRef) else e
                       for e in chain_to_typed_chain(list(reversed(chain)), cgraph, func)]
                      for chains in thing_chains.values()
                      for chain in chains)

    def getLinkers(node, g):
        for list_top in getLists(node, g):
            for linker in g[:owl.oneOf:list_top]:
                yield linker

    def allSubjects(object, graph):
        yield from (s for s, p in graph[::object])
        yield from getLinkers(object, graph)

    print()
    ttc = tchains(terminal_chains, allSubjects)
    tec = tchains(endpoint_chains, allSubjects)
    pprint(ttc)
    pprint(tec)

    valid_tagsets = frozenset((t for s in tag_transitions.values() for t in s))
    tts = valid_tagsets - frozenset(tag_transitions)
    endtype = 'TODO'  # 
    tt = {}
    for endtype, chains  in endpoint_chains.items():
        for *_chain, tag in chains:
            if _chain:
                next_thing = _chain[-1]
            for ets in tts:
                if tag in ets:
                    tt[ets] = next_thing

    terminal_tagsets = tt

    #[print(wat) for wat in terminal_chains.values()]
    #pprint(terminal_chains)
    return tag_types, tag_tokens, partInstances, valid_tagsets, terminal_tagsets, tag_transitions


def curatorTags():
    tag_types, tag_tokens, *rest = parse_workflow()
    return sorted(OntId(t).curie for t in tag_tokens[wf.tagCurator])


def main():
    tag_types, tag_tokens, partInstances, valid_tagsets, terminal_tagsets, tag_transitions = parse_workflow()

    from scibot.config import api_token, username, group, memfile
    get_annos = Memoizer('/tmp/test-stuff.pickle', api_token, username, group)
    annos, last_sync = get_annos.get_annos_from_file()  # there's our 'quick' version
    print('>>>>>>>>>>>>>>>>>>>>>> Done with initial load.')  # pickle is ... not efficient
    annos_dict = {anno.id:anno for anno in annos}
    AnnoAsTags.tag_types = tag_types
    AnnoAsTags.anno_part_instances = partInstances
    AnnoAsTags.tag_transitions = tag_transitions
    AnnoAsTags.valid_tagsets = valid_tagsets
    AnnoAsTags.terminal_tagsets = terminal_tagsets  # {tagset:endtype}
    AnnoAsTags.annos = annos
    AnnoAsTags.annos_dict = annos_dict

    #aat = [TagLogic(a) for a in annos]
    def toprofile():
        out = []
        for a in annos:
             tl = TagLogic(a)
             out.append(tl)
        return out

    aat = toprofile()
    print('>>>>>>>>>>>>>>>>>>>>>> Done with initial processing.')
    warn = [a for a in aat if a.warnings]
    inv = [a for a in aat if a.invalid]

    # 1 reduce everything to updated user tag triples
    # for curators take only the latest reply WITH TAGS
    # sort the tags
    # check against valid end states

    unique_badtags = defaultdict(list)
    for i in inv:
        for b in i.badset:
            if i.invalid:
                unique_badtags[b].append(i)

    unique_badcurator = defaultdict(list)
    for key, value in ((frozenset(i.curator_tags), i) for i in inv):
        unique_badcurator[key].append(value)

    papers = defaultdict(set)
    for r in aat:
        papers[r.uri_normalized].add(r)

    RRIDCURKill = OntId('RRIDCUR:Kill')
    RRIDCURKillPageNote = OntId('RRIDCUR:KillPageNote')
    killed = [a for a in inv if RRIDCURKill in a.tags]
    killed_pn = [a for a in inv if RRIDCURKillPageNote in a.tagset]

    all_ids = {uri:frozenset(t for anno in annos for t in anno.ontid_all_tags) for uri, annos in papers.items()}
    pmids = {uri:[t for t in tags if t.prefix == 'PMID'] for uri, tags in all_ids.items() if [t for t in tags if t.prefix == 'PMID']}
    dois = {uri:[t for t in tags if t.prefix == 'DOI'] for uri, tags in all_ids.items() if [t for t in tags if t.prefix == 'DOI']}
    either = {uri:[t for t in tags if t.prefix in ('DOI', 'PMID')]
              for uri, tags in all_ids.items()
              if [t for t in tags if t.prefix in ('DOI', 'PMID')]}
    dangerzone = {uri:tags for uri, tags in either.items() if len(tags) > 2}
    maybe_both = {uri:tags for uri, tags in either.items() if len(tags) == 2}
    actually_both = {uri:tags for uri, tags in maybe_both.items()
                     if 'PMID' in [t.prefix for t in tags] and 'DOI' in [t.prefix for t in tags]}
    no_pmid = {uri:tags for uri, tags in papers.items() if uri not in pmids}
    no_doi = {uri:tags for uri, tags in papers.items() if uri not in dois}
    no_id = {uri:tags for uri, tags in papers.items() if uri not in either}
    weird_paper_ids = {uri:tags for uri, tags in maybe_both.items() if uri not in actually_both}

    maybe_release = {uri:annos
                     for uri, annos in papers.items()
                     if uri in either and uri not in dangerzone and uri not in weird_paper_ids}
    RRIDcurator = OntId('workflow:RRID')  # because OntId is _really_ slow when used with rdflib.URIRef
    RRIDscibot = OntId('workflow:RRIDscibot')

    # with warnings
    with_warnings = {uri:frozenset([a for a in annos
                                    if a.valid and
                                    (RRIDcurator in a.tagset or RRIDscibot in a.tagset)])
                     for uri, annos in maybe_release.items()}
    ok_warnings_annos = {uri:annos for uri, annos in with_warnings.items() if annos}
    papers_not_ok_warnings = {uri:annos for uri, annos in papers.items() if uri not in ok_warnings_annos}

    # without warnings
    probably_ok_release = {uri:frozenset([a for a in annos  # aka no warnings
                                          if a.valid and not a.warnings and
                                          (RRIDcurator in a.tagset or RRIDscibot in a.tagset)])
                           for uri, annos in maybe_release.items()}
    ok_with_annos = {uri:annos for uri, annos in probably_ok_release.items() if annos}
    papers_not_ok = {uri:annos for uri, annos in papers.items() if uri not in ok_with_annos}


    hh = [HypothesisHelper(a, annos) for a in annos]
    def printBadtagsHtml():
        _ = [print(repr(tag), [HypothesisHelper.byId(a.id).htmlLink for a in annos]) for tag, annos in unique_badtags.items()]

    def printBadtagsShare():
        _ = [print(repr(tag), [HypothesisHelper.byId(a.id).shareLink for a in annos]) for tag, annos in unique_badtags.items()]

    def csvBadtagsShare():
        import csv
        from datetime import date
        #rows = sorted(set((tag, HypothesisHelper.byId(a.id).shareLink) for tag, annos in unique_badtags.items() for a in annos))
        rows = sorted(set((tag, HypothesisHelper.byId(a.id).shareLink) for tag, annos in unique_badtags.items() for a in annos))
        TODAY = date.today().strftime('%Y-%m-%d')
        with open(f'badtag-report-{TODAY}.csv', 'wt', newline='\n') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    rows = sorted(set((tag, HypothesisHelper.byId(a.id).htmlLink, a.reason_invalid)
                      for tag, annos in unique_badtags.items() for a in annos))
    wat = sorted(set((tag, HypothesisHelper.byId(a.id)) for tag, annos in unique_badtags.items() for a in annos))
    def maxp(r):
        return maxp(r.parent) if r.parent else r

    hrm = [maxp(w) for _, w in wat if TagLogic.byId(w.id).Duplicate]
    misp_but_not_why = [[t, maxp(w), TagLogic.byId(w.id).reason_invalid]
                        for t, w in wat
                        if t == 'RRIDCUR:Misplaced']
    dupe_but_not_why = [[t, maxp(w), TagLogic.byId(w.id).reason_invalid]
                        for t, w in wat
                        if t == 'RRIDCUR:Duplicate']


    def check_uri_norm(substring, viewkey=True):
        return sorted(k if viewkey else tuple(sorted(set(_.uri for _ in v))) for k, v in papers.items() if substring in k)

    report = f"""
    Records
    total:       {len(aat)}
    annotations: {len([a for a in aat if a.isAnnotation])}
    page notes:  {len([a for a in aat if a.isPageNote])}
    replies:     {len([a for a in aat if a.isReply])}
    warnings:    {len(warn)}
    invalid:     {len(inv)}
    valid:       {len([a for a in aat if a.valid])}


    Papers
    norm uris:  {len(papers)}
    good both:  {len(actually_both)}
    no pmid:    {len(no_pmid)}
    no doi:     {len(no_doi)}
    no id:      {len(no_id)}
    """
    print(report)
    embed()
    return

def old_main():
    class Werk(HypothesisHelper):
        _annos = {}
        _replies = {}
        objects = {}
        _papers = None
        _dois = None
        _pmids = None
        _done_all = False

        @property
        def type(self):
            return self._anno.type

        @property
        def user(self):
            return self._anno.user

        @property
        def anno(self):
            return self._anno.updated

        @property
        def uri(self):
            return self._anno.uri

        
    get_annos = Memoizer(memfile, api_token, username, group, 200000)
    annos = get_annos.get_annos_from_file()  # there's our 'quick' version

    _ = [Werk(a, annos) for a in annos]

    heads = [[(w.uri, a.updated, a.user, t, a.htmlLink)
              for a in {w}.union(w.replies)
              for t in a.tags]
             for w in Werk
             if w.type == 'annotation' and
             # old pmiding style
             not any('PMID:' in t for t in w.tags)]

    #[[(uri, user, tag) for uri, time, user, tag in h] for h in heads]

    def wat(thing):
        raise ValueError(f'{thing} not len 1')

    uri_to_pmid = {w.uri: maybe_pmid[0] if len(maybe_pmid) == 1 else wat(maybe_pmid)
                   for w in Werk
                   for maybe_pmid in [[t for t in w.tags if 'PMID:' in t]]
                   if maybe_pmid}

    uri_to_doi = {w.uri: maybe_doi[0] if len(maybe_doi) == 1 else wat(maybe_doi)
                   for w in Werk
                   for maybe_doi in [[t for t in w.tags if 'DOI:' in t]]
                   if maybe_doi}

    uris = sorted(set(w.uri for w in Werk))


    a = sorted([(time,
                 uri,
                 uri_to_doi.get(uri, None),
                 uri_to_pmid.get(uri, None),
                 user,
                 tag,
                 link,)
                for uri, time, user, tag, link in h]
               for h in heads)

    # this is the naieve version that doesn't require non-local informaition to resolve
    # in reality we need to use Curation to get the paper and all that other fun stuff

    multiple_tags = [_ for _ in a if len(_) > 1]
    single_tag = [_ for _ in a if len(_) == 1]
    print('multiple', len(multiple_tags), 'single', len(single_tag))

    # sort all of these by time and replay them
    # so that we get the algorithem right for the streaming case
    # and then scream of people edit their annotations becuase update is no fun

    embed()


if __name__ == '__main__':
    main()
