import re
import requests
from bs4 import BeautifulSoup
from scibot.utils import makeSimpleLogger

log = makeSimpleLogger('extract')


# utility
def col0(pairs): return list(zip(*pairs))[0]
def col1(pairs): return list(zip(*pairs))[1]

# prefixes

agprefixes = (
    ('Addgene', 'Addgene'),
    ('addgene', 'Addgene'),
    ('plasmid', 'Addgene'),
    ('Plasmid', 'Addgene'),
    ('addgene cat', 'Addgene'),
    ('addgene.org', 'Addgene'),
    ('addgene ID', 'Addgene'),  # probably won't work
    ('addgene cat. no.', 'Addgene'),
    ('Jackson Laboratory Cat', 'IMSR_JAX'),
    ('Jackson Laboratory	Cat', 'IMSR_JAX'),
    ('Jackson Laboratory Stock', 'IMSR_JAX'),
    ('Jackson Laboratory	Stock', 'IMSR_JAX'),
    ('The Jackson Laboratory', 'IMSR_JAX'),
    ('The Jackson Laboratory Stock', 'IMSR_JAX'),
    ('The Jackson Laboratory	Stock', 'IMSR_JAX'),
    ('The Jackson Laboratory Cat', 'IMSR_JAX'),
    ('The Jackson Laboratory	Cat', 'IMSR_JAX'),
    ('Jackson Laboratories Cat', 'IMSR_JAX'),
    ('Jackson Laboratories	Cat', 'IMSR_JAX'),
)

prefixes = (
    ('AB', 'AB'),
    ('AGSC', 'AGSC'),
    ('ARC', 'IMSR_ARC'),
    ('BCBC', 'BCBC'),
    ('BDSC', 'BDSC'),
    ('DGRC', 'DGRC'),
    ('CGC', 'CGC'),
    ('CRL', 'IMSR_CRL'),
    #('CVCL', 'CVCL'),  # numbers + letters :/
    ('DGGR', 'DGGR'),
    ('FBst', 'FBst'),
    ('FlyBase', 'FlyBase'),
    ('HAR', 'IMSR_HAR'),
    ('JAX', 'IMSR_JAX'),
    ('KOMP', 'IMSR_KOMP'),
    ('MGI', 'MGI'),
    ('MMRRC', 'MMRRC'),
    ('NCIMR', 'IMSR_NCIMR'),
    ('NSRRC', 'NSRRC'),
    ('NXR', 'NXR'),
    ('RBRC', 'IMSR_RBRC'),
    ('RGD', 'RGD'),
    ('SCR', 'SCR'),
    ('TAC', 'IMSR_TAC'),
    ('TIGM', 'IMSR_TIGM'),
    ('TSC', 'TSC'),
    ('WB-STRAIN', 'WB-STRAIN'),
    ('WTSI', 'IMSR_WTSI'),
    ('ZDB', 'ZFIN_ZDB'),
    ('ZFIN', 'ZFIN'),
    ('ZIRC', 'ZIRC'),
)
prefix_lookup = {k:v for k, v in prefixes}
prefix_lookup['CVCL'] = 'CVCL'  # ah special cases
prefix_lookup.update({k:v for k, v in agprefixes})

# paper identifiers

def searchSoup(soup):
    def search(tag, prop, val, key, additional_prop_vals=None):
        if additional_prop_vals is None:
            pvs = {prop:val}
        else:
            additional_prop_vals.update({prop:val})
            pvs = additional_prop_vals
        matches = soup.find_all(tag, pvs)
        if matches:
            return matches[0][key]
    return search


def normalizeDoi(doi):
    doi = doi.replace(' ', '')
    if 'http' in doi or 'doi.org' in doi:
        doi = '10.' + doi.split('.org/10.', 1)[-1]
    elif doi.startswith('doi:'):
        doi = doi.strip('doi:')
    elif doi.startswith('DOI:'):
        doi = doi.strip('DOI:')
    return doi


def getDoi(*soups):
    argslist = (  # these go in order so best returns first
        # TODO bind a handler for these as well...
        ('meta', 'name', 'DC.Identifier', 'content'),  # elife pmc etc.
        ('meta', 'name', 'DOI', 'content'),  # nature pref
        ('meta', 'name', 'dc.identifier', 'content'),  # nature
        ('meta', 'name', 'citation_doi', 'content'), # wiley jove f1000 ok
        ('a', 'class', 'doi', 'href'),  # evilier
        ('a', 'class', 'S_C_ddDoi', 'href'),  # evilier
        ('a', 'id', 'ddDoi', 'href'),  # evilier
        ('meta', 'name', 'DC.identifier', 'content'),  # f1000 worst
        ('meta', 'name', 'dc.Identifier', 'content', {'scheme':'doi'}),  # tandf
        ('meta', 'name', 'dc.Source', 'content'),  # mit press jounals wat
        ('meta', 'name', 'dc.identifier', 'content'),
        ('meta', 'name', 'prism.doi', 'content'),
    )
    for soup in soups:
        for args in argslist:
            doi = searchSoup(soup)(*args)
            if doi is not None:
                return normalizeDoi(doi)


def getUri(uri, *soups):
    argslist = (
        ('meta', 'property', 'og:url', 'content'),  # FIXME mitpressjournals has an idiot in it somewhere
        ('link', 'rel', 'canonical', 'href'),
    )
    for soup in soups:
        for args in argslist:
            cu = searchSoup(soup)(*args)
            if cu is not None and cu.startswith('http'):
                if cu != uri:
                    log.warning('canonical and uri do not match, '
                                f'preferring canonical\n{cu}\n{uri}')
                return cu
    return uri


def getPmid(*soups):
    argslist = (
        ('meta', 'property', 'citation_pmid', 'content'),
    )
    for soup in soups:
        for args in argslist:
            cu = searchSoup(soup)(*args)
            if cu is not None:
                return cu  # FIXME TODO yeild here


def getTitle(*soups):
    for soup in soups:
        for t in soup.find_all('title'):
            yield t.text


def chooseTitle(document, titles):
    meta_titles = []
    for k, d_ in document.items():
        rank = 0  # TODO
        if 'title' in d_:
            t = d_['title'][0]  # FIXME warn on > 1 ?
            meta_titles.append((rank, t))

    if meta_titles:
        title = sorted(meta_titles)[0][1]

    elif titles:
        title = sorted(titles, key=lambda t: -len(t))[0]

    else:
        log.warning(f'no title for {document}')
        title = 'Spooky nameless page'

    document['title'] = title


def getLinks(*soups):
    for soup in soups:
        for l in soup.find_all('link'):
            yield l.attrs


def chooseLinks(document, links):
    meta_links = []
    for link in links:
        if 'rel' in link and 'canonical' in link['rel']:
            l = {'rel': 'canonical', 'href': link['href']}
            if 'type' in link and link['type']:
                l['type'] = link['type']

            meta_links.append(l)

    # TODO pull out other links as well
    document['link'].extend(meta_links)


def searchSoups(argslist, *soups):
     for soup in soups:
        for args in argslist:
            cu = searchSoup(soup)(*args)
            if cu is not None:
                yield cu


def getDocument(target_uri, *soups):
    # TODO probably want to detect when there are tags in the header that
    # we are missing/skipping since this takes a closed world approach to detection
    # rather than prefix based detection
    # TODO pull these out into a more visible file
    dc_fields = 'identifier', 'title', 'publisher', 'format', 'creator', 'date'
    eprints_fields = ('title', 'creators_name', 'type', 'datestamp', 'ispublished',
                      'date', 'date_type', 'publication', 'volume', 'pagerange')
    prism_fields = ('volume', 'number', 'startingPage', 'endingPage', 'publicationName',
                    'issn', 'publicationDate', 'doi')
    highwire_fields = ('title', 'journal_title', 'publisher', 'issue', 'volume', 'doi',
                       'firstpage', 'lastpage', 'date', 'abstract_html_url', 'fulltext_html_url',
                       'pdf_url', 'pii', 'article_type', 'online_date', 'publication_date',
                       'issn', 'keywords', 'language', 'author', 'author_institution', 
    )
    og_fields = ('title', 'type', 'image', 'url', 'audio', 'description', 'determiner',
                 'locale', 'locale:alternate', 'site_name', 'video')

    def dmeta(rexp, fields, props=('name',)):
        return {field: [('meta', prop, re.compile(rexp.format(field=field), re.I), 'content')
                        for prop in props] for field in fields}

    todo = {
        'dc': dmeta('^(dc|dcterms).{field}$', dc_fields),
        'eprints': dmeta('^eprints.{field}$', eprints_fields),
        'facebook': dmeta('^og:{field}$', og_fields, props=('name', 'property')),
        # some people use name for og instead of property (spec expects property)
        'highwire': dmeta('^citation_{field}$', highwire_fields),
        'prism': dmeta('^prism.{field}$', prism_fields),
        'twitter':{},  # TODO??
    }

    document = {key: {field: results
                      for field, argslist in dict_.items()
                      for results in (list(searchSoups(argslist, *soups)),)
                      if results}
                for key, dict_ in todo.items()}

    doi = getDoi(*soups)
    pmid = getPmid(*soups)
    titles =  list(getTitle(*soups))
    chooseTitle(document, titles)
    links = list(getLinks(*soups))
    document['link'] = [{'href': target_uri}]
    chooseLinks(document, links)
    return document, doi, pmid


def document_from_url(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'lxml')
    return getDocument(url, resp, soup), soup


# rrids

def clean_text(text):
    # cleanup the inner text
    text = text.replace('–','-')
    text = text.replace('‐','-')  # what the wat
    text = text.replace('\xa0',' ')  # nonbreaking space fix

    mids = (r'',
            r'\ ',
            r'_\ ',
            r'\ _',
            r': ',
            r'-',
           )
    tail = r'([\s,;\)])'
    replace = r'\1\2_\3\4'
    def make_cartesian_product(prefix, suffix=r'(\d+)'):
        return [(prefix + mid + suffix + tail, replace) for mid in mids]

    fixes = []
    prefixes_digit = [r'([^\w])(%s)' % _ for _ in ('AB', 'SCR', 'MGI')]
    for p in prefixes_digit:
        fixes.extend(make_cartesian_product(p))
    fixes.extend(make_cartesian_product(r'([^\w])(CVCL)', r'([0-9A-Z]+)'))  # FIXME r'(\w{0,5})' better \w+ ok
    fixes.append((r'\(RRID\):', r'RRID:'))

    for f, r in fixes:
        text = re.sub(f, r, text)
    return text


def find_rrids(text):
    # first round
    regex1 = '(.{0,32})(RRID(:|\)*,*)[ \t]*)(\w+[_\-:]+[\w\-]+)([^\w].{0,31})'
    matches = re.findall(regex1, text)
    for prefix, rrid, sep, id_, suffix in matches:
        #print((prefix, rrid, sep, id_, suffix))
        exact = 'RRID:' + id_
        exact_for_hypothesis = exact
        yield prefix, exact, exact_for_hypothesis, suffix

    # second round
    orblock = '(' + '|'.join(col0(prefixes)) + ')'
    sep = '(:|_)([ \t]*)'
    agsep = '([ \t]*#)([ \t]*)'  # FIXME doesn't work with "Stock No." or "Stock No:"
    agorblock = '(' + '|'.join(col0(agprefixes)) + ')'
    regex2 = ('(.{0,32})(?:' + orblock + f'{sep}(\d+)|(CVCL){sep}(\w+)|'
              + agorblock + f'{agsep}(\w+))([^\w].{{0,31}})')  # the first 0,32 always greedy matches???
    matches2 = re.findall(regex2, text)  # FIXME this doesn't work since our prefix/suffix can be 'wrong'
    for (prefix, namespace, sep, spaces, nums,
         cvcl, cvcl_sep, cvcl_spaces, cvcl_nums,
         ag, ag_sep, ag_spaces, ag_nums,
         suffix) in matches2:
        if cvcl:
            #print('\t\t', (prefix, namespace, sep, spaces, nums, cvcl, cvcl_sep, cvcl_spaces, cvcl_nums, suffix))
            namespace, sep, spaces, nums = cvcl, cvcl_sep, cvcl_spaces, cvcl_nums  # sigh
        elif ag:
            namespace, sep, spaces, nums = ag, ag_sep, ag_spaces, ag_nums  # sigh
        if re.match(regex1, ''.join((prefix, namespace, sep, spaces, nums, suffix))) is not None:
            #print('already matched')
            continue  # already caught it above and don't want to add it again
        if ag:  # switch sep for addgene after match
            sep = '_'
        exact_for_hypothesis = namespace + sep + nums
        resolver_namespace = prefix_lookup[namespace]
        exact = 'RRID:' + resolver_namespace + sep + nums
        yield prefix, exact, exact_for_hypothesis, suffix

    # third round for BDSC
    regex3 = '(.{0,32})(BDSC|BL|Bl|Bloomington)(\s?)(stock)?(\s)?(#|no|no\.)?(\s?)([0-9]{2,10})([^\w].{0,31})'
    matches3 = re.findall(regex3, text)
    for prefix, a, b, c, d, e, f, nums, suffix in matches3:
        if nums in ['17', '21']:
            # special case to avoid false positives
            continue
        yield prefix, f'RRID:BDSC_{nums.strip()}', f'{a}{b}{c}{d}{e}{f}{nums}', suffix

    # fourth round for SAMN
    regex4 = '(.{0,32})(SAMN)(\s?)([0-9]{3,15})([^\w].{0,31})'
    matches4 = re.findall(regex4, text)
    for prefix, a, b, nums, suffix in matches4:
        yield prefix, f'RRID:SAMN{nums.strip()}', f'{a}{b}{nums}', suffix


# extract from post

def process_POST_request(request):
    dict_ = dict(request.form)
    def htmlify(thing):
        try:
            html = dict_[thing]
        except KeyError as e:
            html = ''
        return '<html>' + html + '</html>'
    uri = dict_['uri']
    head = htmlify('head')
    body = htmlify('body')
    try:
        text = dict_['data']
    except KeyError as e:
        text = ''

    headsoup = BeautifulSoup(head, 'lxml')
    bodysoup = BeautifulSoup(body, 'lxml')

    target_uri = getUri(uri, headsoup, bodysoup)
    #doi = getDoi(headsoup, bodysoup)
    #pmid = getPmid(headsoup, bodysoup)
    document, doi, pmid = getDocument(target_uri, headsoup, bodysoup)
    cleaned_text = clean_text(text)
    return target_uri, document, doi, pmid, head, body, text, cleaned_text


class PaperId:
    id_types = (
        'uri_normalized',
        'doi',
        'pmid',
        'hypothesis_normalized',
        'uri',
    )
    def __init__(self,
                 uri_normalized,
                 doi=None,
                 pmid=None,
                 hypothesis_normalized=None,
                 uri=None):

        # names
        self.uri_normalized = uri_normalized
        self.doi = OntId(doi) if doi else doi
        self.pmid = OntId(pmid) if pmid else pmid
        self.hypothesis_normalized = hypothesis_normalized
        self.uri = uri

        # amusingly the actual identities
        self.urn = None  # pdf fingerprint
        self.text_hash = None
        self.html_hash = None
        self.head_hash = None
        self.body_hash = None
        self.jats_hash = None
        self.stripped_hash = None

    @property
    def _existing_ids(self):
        for id_type in self.id_types:
            id = getattr(self, id_type, None)
            if id is not None:
                yield id

    @property
    def existing_ids(self):
        return set(self._existing_ids)

    @property
    def _resolvable_ids(self):
        yield self.doi.iri
        yield self.uri

    @property
    def resolvable_ids(self):
        return set(self._resolvable_ids)

    @property
    def _chains(self):
        for id in self.resolvable_ids:
            yield id, tuple(resolution_chain(id))

    @property
    def chains(self):
        return {id:chain for id, chain in self._chains}

    def idPaper(self):
        if self.doi is None:
            paper = self
            doi = paper['DOI']
            pmid = paper['PMID']
            log.info(url)
            if not self.doi and self.uri.startswith('http'):  # we've go some weird ones in there...
                doi = scrapeDoi(uri)
                # scrapeIds(uri)
                if doi is not None:
                    log.info(doi)
                    pmid = get_pmid(doi)
                    log.warning('json malformed in get_pmid')
                    log.info(pmid)
                    resp = annotate_doi_pmid(url, doi, pmid, rrcu.h_curation, [])
                    log.info('new doi')
                    return resp
            else:
                log.info(doi)
                log.info('already found')

    def scrapeDoi(self):
        env = os.environ.copy()
        cmd_line = ['timeout', '30s', 'google-chrome-unstable', '--headless', '--dump-dom', url]
        p = subprocess.Popen(cmd_line, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             env=env)
        out, err = p.communicate()
        if p.returncode:
            log.critical('UTOH')
            return None
        elif b'ERROR:headless_shell.cc' in out:
            log.critical(out)
            raise IOError('Something is wrong...')
        qurl = quote(url, '')
        if len(qurl) > 200:
            qurl = qurl[:200]
        with open(os.path.expanduser(f'~/files/scibot/{qurl}'), 'wb') as f:
            f.write(out)
        both = BeautifulSoup(out, 'lxml')
        doi = getDoi(both, both)
        return doi





