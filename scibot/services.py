import requests
from bs4 import BeautifulSoup
from scibot.utils import log
try:
    from urllib.parse import urlencode, quote
except ImportError:
    from urllib import urlencode, quote

# existing identifiers and rrids

def existing_tags(target_uri, h):
    params = {
        'limit':200,
        'uri':target_uri,
        'group':h.group,
        'user':h.username,
    }
    query_url = h.query_url_template.format(query=urlencode(params, True))
    obj = h.authenticated_api_query(query_url)
    rows = obj['rows']
    tags = {}
    unresolved_exacts = {}
    for row in rows:
        # FIXME make sure that target_uri actually matches the URI returned here!
        # it is ok to to have multiple page notes appear as a result because we
        # don't have access to hypothes.is's document table
        for tag in row['tags']:
            if tag.startswith('RRID:'):
                tags[tag] = row['id']
            elif tag.startswith('PMID:'):
                tags[tag] = row['id']
            elif tag.startswith('DOI:'):
                tags[tag] = row['id']
            elif tag == 'RRIDCUR:Unresolved':
                unresolved_exacts[row['target'][0]['selector'][0]['exact']] = row['id']
    return tags, unresolved_exacts

# PMIDs

def get_pmid(doi):  # TODO
    url = f'https://www.ncbi.nlm.nih.gov/pubmed/?term={quote(doi)}[Location ID]&report=uilist&format=text'
    body = requests.get(url).text
    soup = BeautifulSoup(body, 'lxml')
    matches = soup.find_all('pre')
    if matches:
        pmid = matches[0].get_text().strip()
        if '\n' in pmid:  # in the event that we get multiple PMIDs it means something is wrong
            pmid = None
        if pmid:
            log.info(f'got pmid from pubmed: {pmid}')
            return 'PMID:' + pmid
    params={'idtype':'auto', 'format':'json', 'Ids':doi, 'convert-button':'Convert'}
    pj = requests.post('https://www.ncbi.nlm.nih.gov/pmc/pmctopmid/', params=params).json()
    log.debug(pj)
    for rec in pj['records']:
        try:
            return 'PMID:' + rec['pmid']
        except KeyError:
            pass

# RRIDs

def rrid_resolver_xml(exact, found_rrids):
    print('\t' + exact)
    resolver_uri = 'https://scicrunch.org/resolver/%s.xml' % exact
    r = requests.get(resolver_uri)
    status_code = r.status_code
    xml = r.content
    print(status_code)
    found_rrids[exact] = status_code
    return xml, status_code, resolver_uri
