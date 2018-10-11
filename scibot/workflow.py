# asdf

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
        return self.user == 'scibot'
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
        Anno('scibot', 'AB_000000', ['RRID:AB_000000']),
        Anno('scibot', 'AB_000001', ['RRIDCUR:Unresolved']),
        Anno('tgbugs', 'metadata', ['RRIDCUR:Missing', 'RRID:AB_123456']),
    ]

    w = [Workflow(a) for a in annos]


class DashboardState:
    def __init__(self, states):
        pass

    def add_anno(self, anno):
        pass


class AnnoAsTags:
    def __init__(self, anno):
        self.anno = anno

    def exact(self):
        pass

    @property
    def RRID(self):
        pass

    def pageNote(self):
        pass

    def putativeRRID(self):
        pass


def write(graph, path, format='nifttl'):
    with open(path, 'wb') as f:
        f.write(graph.serialize(format=format))


def main():
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
    #from rdflib.extras import infixowl as io

    from pyontutils.graphml_to_ttl import WorkflowMapping, PaperIdMapping

    docs = Path(__file__).parent.absolute().resolve().parent / 'docs'
    rridpath = docs / 'workflow-rrid.graphml'
    paperpath = docs / 'workflow-paper-id.graphml'

    cgraph = ConjunctiveGraph()
    gt.WorkflowMapping(rridpath.as_posix()).graph(cgraph)
    gt.PaperIdMapping(paperpath.as_posix(), False).graph(cgraph)
    write(cgraph, '/tmp/workflow.ttl')
    predicates = set(cgraph.predicates())
    OntCuries({cp:str(ip) for cp, ip in cgraph.namespaces()})
    hg = makeGraph('', graph=cgraph)
    short = sorted(hg.qname(_) for _ in predicates)

    wf.hasTag
    wf.hasReplyTag
    wf.hasTagOrReplyTag
    wf.hasOutputTag

    #if type isa wf.tag

    tag_types = set(cgraph.transitive_subjects(rdfs.subClassOf, wf.tag))
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
                                  for t in cgraph.transitive_subjects(rdf.type, a)) for a in annoParts}

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
                print(tc.yellow(p))
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

    #[print(wat) for wat in terminal_chains.values()]
    #pprint(terminal_chains)
    embed()
    return

    # 1 reduce everything to updated user tag triples
    # for curators take only the latest reply WITH TAGS
    # sort the tags
    # check against valid end states
    from hyputils.hypothesis import Memoizer, HypothesisHelper
    from scibot.config import api_token, username, group, memfile

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
