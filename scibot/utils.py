import requests
from .uri import normalize as uri_normalize
from pyontutils.utils import Async, deferred, chunk_list, anyMembers, noneMembers, makeSimpleLogger
try:
    breakpoint
except NameError:
    from IPython import embed as breakpoint

log = makeSimpleLogger('scibot')
logd = log.getChild('data')

from hyputils.hypothesis import log as _hlog
_hlog.removeHandler(_hlog.handlers[0])
_hlog.addHandler(log.handlers[0])


class ResolutionError(Exception):
    """ something messed up """


def DOI(doi):
    return 'https://doi.org/' + doi


def PMID(pmid):
    return pmid.replace('PMID:', 'https://www.ncbi.nlm.nih.gov/pubmed/')


def rrid_from_citation(citation):
    _, suffix_stuff = citation.split('RRID:')
    suffix = suffix_stuff.rstrip(')')
    return 'RRID:' + suffix


def get_pmid_from_url(url):
    if anyMembers(url,
                  'www.ncbi.nlm.nih.gov/pubmed/',
                  'europepmc.org/abstract/MED/'):
        # TODO validate the suffix
        _, suffix = url.rsplit('/', 1)
        return 'PMID:' + suffix


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
    breakpoint()


def resolution_chain(iri):
    #doi = doi  # TODO
    s = requests.Session()
    head = requests.head(iri)
    yield head.url
    while head.is_redirect and head.status_code < 400:  # FIXME redirect loop issue
        yield head.next.url
        head = s.send(head.next)
        yield head.url
        if not head.is_redirect:
            break

    if head.status_code >= 400:
        raise ResolutionError(f'Nothing found at {head.url}\n')


bad_uris = ('/articles/6-124/v2',  # FIXME don't hardcode this >_<
            '//bmcbiol.biomedcentral.com/articles/10.1186/s12915-016-0257-2')


def uri_normalization(uri):
    """ NOTE: this does NOT produce uris """
    try:
        # strip hypothesis extension prefix
        if uri.startswith('chrome-extension://bjfhmglciegochdpefhhlphglcehbmek/content/web/viewer.html?file='):
            junk, uri = uri.split('=', 1)

        # universal fixes
        no_fragment, *_frag = uri.rsplit('#', 1)
        no_trailing_slash = no_fragment.rstrip('/')  # annoying
        _scheme, no_scheme = no_trailing_slash.split('://', 1)

        # special cases
        if 'frontiersin.org' in no_scheme:
            # og:url on frontiers is incorrect
            no_scheme = no_scheme.replace('article/', 'articles/')
        elif 'fasebj.org' in no_scheme:  # FIXME this one has _all_ the variants :/
            no_scheme = (no_scheme
                         .replace('.abstract', '')
                         .replace('.full', '')
                         .replace('.pdf', '')
            )
        elif no_scheme.endswith('?needAccess=true'):
            no_scheme = no_scheme[:-len('?needAccess=true')]
        elif '?systemMessage' in no_scheme:
            no_scheme, junk = no_scheme.rsplit('?systemMessage', 1)

        # specific fixes
        if anyMembers(no_scheme,
                      'acs.org',
                      'ahajournals.org',
                      'biologicalpsychiatryjournal.com',
                      'ebiomedicine.com',
                      'fasebj.org',
                      'frontiersin.org',
                      'future-science.com',
                      'hindawi.com',
                      'ieee.org',
                      'jclinepi.com',
                      'jpeds.com',
                      'liebertpub.com',
                      'mitpressjournals.org',
                      'molbiolcell.org',
                      'molmetab.com',
                      'neurobiologyofaging.org',
                      'physiology.org',
                      'sagepub.com',
                      'sciencedirect.com',
                      'tandfonline.com',
                      'theriojournal.com',
                      'wiley.com',):
            # NOTE not all the above hit all of these
            # almost all still resolve
            normalized = (no_scheme
                          .replace('/abstract', '')
                          .replace('/abs', '')
                          .replace('/fulltext', '')
                          .replace('/full', '')
                          .replace('/pdf', ''))
        #elif ('sciencedirect.com' in no_scheme):
            #normalized = (no_scheme
                          #.replace('/abs', ''))
        elif ('cell.com' in no_scheme):
            normalized = (no_scheme  # FIXME looks like cell uses /abstract in og:url
                          .replace('/abstract', '/XXX')
                          .replace('/fulltext', '/XXX'))
        elif 'jneurosci.org' in no_scheme:
            # TODO content/early -> resolution_chain(doi)
            normalized = (no_scheme
                          .replace('.short', '')
                          .replace('.long', '')
                          .replace('.full', '')
                          .replace('.pdf', '')
                          # note .full.pdf is a thing
                          )
        elif 'pnas.org' in no_scheme:
            normalized = (no_scheme
                          .replace('.short', '')
                          .replace('.long', '')
                          .replace('.full', ''))
        elif 'mdpi.com' in no_scheme:
            normalized = (no_scheme
                          .replace('/htm', ''))
        elif 'f1000research.com' in no_scheme:
            # you should be ashamed of yourselves for being in here for this reason
            normalized, *maybe_version = no_scheme.rsplit('/v', 1)
        elif 'academic.oup.com' in no_scheme:
            normalized, *maybesr = no_scheme.rsplit('?searchresult=', 1)
            _normalized, maybe_junk = normalized.rsplit('/', 1)
            numbers = '0123456789'
            if (maybe_junk[0] not in numbers or  # various ways to detect the human readable junk after the id
                maybe_junk[-1] not in numbers or
                '-' in maybe_junk or
                len(maybe_junk) > 20):
                normalized = _normalized
        elif anyMembers(no_scheme,
                        'jci.org',
                        'nature.com'):
            # cases where safe to remove query fragment
            normalized, *_query = no_scheme.rsplit('?', 1)
            normalized, *table_number = normalized.rsplit('/tables/', 1)
        elif 'pubmed/?term=' in no_scheme and noneMembers(no_scheme, ' ', '+'):
            normalized = no_scheme.replace('?term=', '')
        elif 'nih.gov/pubmed/?' in no_scheme:
            # FIXME scibot vs client norm?
            normalized = no_scheme.replace(' ', '+')
        elif 'govhttp' in no_scheme:
            # lol oh dear
            hrm, oops = no_scheme.split('govhttp')
            ded, wat = oops.split('//', 1)
            blargh, suffix = wat.split('/', 1)
            normalized = hrm + 'gov/pmc/' + suffix
        elif 'table/undtbl' in no_scheme:
            normalized, table_number = no_scheme.rsplit('table/undtbl')
        elif anyMembers(no_scheme,
                        'index.php?',
                       ):
            # cases where we just use hypothes.is normalization
            _scheme, normalized = uri_normalize(uri).split('://')  # FIXME h dependency
        else:
            normalized = no_scheme

        'onlinelibrary.wiley.com/doi/10.1002/cne.23727?wol1URL=/doi/10.1002/cne.23727&regionCode=US-CA&identityKey=e2523300-b934-48c9-b08e-940de05d7335'
        'www.jove.com/video/55441/?language=Japanese'
        'www.nature.com/neuro/journal/v19/n5/full/nn.4282.html'
        'www.nature.com/cr/journal/vaop/ncurrent/full/cr201669a.html'
        'https://www.nature.com/articles/cr201669'

        #{'www.ingentaconnect.com/content/umrsmas/bullmar/2017/00000093/00000002/art00006':
         #[OntId('DOI:10.5343/bms.2016.1044'), OntId('DOI:info:doi/10.5343/bms.2016.1044')]}

        # pmid extract from pmc
        #<meta name="citation_pmid" content="28955177">
        return normalized


    except ValueError as e:  # split fail
        pdf_prefix = 'urn:x-pdf:'
        if uri.startswith(pdf_prefix):
            return uri
        elif uri in bad_uris:
            print('AAAAAAAAAAAAAAAAAAAAAAAAAAA', uri)
            return 'THIS URI IS GARBAGE AND THIS IS ITS NORMALIZED FORM'
        else:
            raise TypeError(uri) from e


def disambiguate_uris(uris):
    dd = defaultdict(set)
    _ = [dd[uri_normalization(uri)].add(uri) for uri in uris if uri not in bad_uris]
    return dict(dd)


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
