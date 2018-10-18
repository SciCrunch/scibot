import re
from bs4 import BeautifulSoup

# utility
def col0(pairs): return list(zip(*pairs))[0]
def col1(pairs): return list(zip(*pairs))[1]

# prefixes
prefixes = (
    ('AB', 'AB'),
    ('AGSC', 'AGSC'),
    ('ARC', 'IMSR_ARC'),
    ('BCBC', 'BCBC'),
    ('BDSC', 'BDSC'),
    ('CGC', 'CGC'),
    ('CRL', 'IMSR_CRL'),
    #('CVCL', 'CVCL'),  # numbers + letters :/
    ('DGGR', 'DGGR'),
    ('EM', 'IMSR_EM'),
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
    ('WB', 'WB'),
    ('WB-STRAIN', 'WB-STRAIN'),
    ('WTSI', 'IMSR_WTSI'),
    ('ZDB', 'ZFIN_ZDB'),
    ('ZFIN', 'ZFIN'),
    ('ZIRC', 'ZIRC'),
)
prefix_lookup = {k:v for k, v in prefixes}
prefix_lookup['CVCL'] = 'CVCL'  # ah special cases

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
                if 'http' in doi:
                    doi = '10.' + doi.split('.org/10.', 1)[-1]
                elif doi.startswith('doi:'):
                    doi = doi.strip('doi:')
                elif doi.startswith('DOI:'):
                    doi = doi.strip('DOI:')
                return doi


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
                    print('canonical and uri do not match, preferring canonical', cu, uri)
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
                yield cu

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
    regex2 = '(.{0,32})(?:' + orblock + '{sep}(\d+)|(CVCL){sep}(\w+))([^\w].{{0,31}})'.format(sep=sep)  # the first 0,32 always greedy matches???
    matches2 = re.findall(regex2, text)  # FIXME this doesn't work since our prefix/suffix can be 'wrong'
    for prefix, namespace, sep, spaces, nums, cvcl, cvcl_sep, cvcl_spaces, cvcl_nums, suffix in matches2:
        if cvcl:
            #print('\t\t', (prefix, namespace, sep, spaces, nums, cvcl, cvcl_sep, cvcl_spaces, cvcl_nums, suffix))
            namespace, sep, spaces, nums = cvcl, cvcl_sep, cvcl_spaces, cvcl_nums  # sigh
        if re.match(regex1, ''.join((prefix, namespace, sep, spaces, nums, suffix))) is not None:
            #print('already matched')
            continue  # already caught it above and don't want to add it again
        exact_for_hypothesis = namespace + sep + nums
        resolver_namespace = prefix_lookup[namespace]
        exact = 'RRID:' + resolver_namespace + sep + nums
        yield prefix, exact, exact_for_hypothesis, suffix

# extract from post

def process_POST_request(request):
    dict_ = dict(request.form)
    def htmlify(thing):
        try:
            html = dict_[thing][0]
        except KeyError as e:
            html = ''
        return '<html>' + html + '</html>'
    uri = dict_['uri'][0]
    head = htmlify('head')
    body = htmlify('body')
    try:
        text = dict_['data'][0]
    except KeyError as e:
        text = ''

    headsoup = BeautifulSoup(head, 'lxml')
    bodysoup = BeautifulSoup(body, 'lxml')

    target_uri = getUri(uri, headsoup, bodysoup)
    doi = getDoi(headsoup, bodysoup)
    pmid = getPmid(headsoup, bodysoup)
    cleaned_text = clean_text(text)
    return target_uri, doi, pmid, head, body, text, cleaned_text



