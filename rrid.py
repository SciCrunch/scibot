#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
from __future__ import print_function
import requests, re, traceback, pyramid
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
try:
    import urlparse
except ImportError:  # python3
    from urllib import parse as urlparse
from os import environ
from io import StringIO
from datetime import datetime
import csv
import ssl
import gzip
import json
import pprint
from typing import Callable, Iterable, Tuple, Any, Generator
from lxml import etree
from curio import Channel, run
from pyramid.response import Response
from hyputils.hypothesis import HypothesisUtils
from export import export_impl, export_json_impl
from IPython import embed
from bs4 import BeautifulSoup

api_token = environ.get('RRIDBOT_API_TOKEN', 'TOKEN')  # Hypothesis API dev token
username = environ.get('RRIDBOT_USERNAME', 'USERNAME') # Hypothesis username
group = environ.get('RRIDBOT_GROUP', '__world__')
group2 = environ.get('RRIDBOT_GROUP2', '__world__')
syncword = environ.get('RRIDBOT_SYNC')

print(username, group, group2)  # sanity check

prod_username = 'scibot'  # nasty hardcode

if 0:#username == prod_username:
    host = '0.0.0.0'
    port = 443

else: 
    print('no login detected, running on localhost only')
    host = 'localhost'
    port = 4443

host_port = 'https://' + host + ':' + str(port)

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

# synchronization setup
async def producer():
    chan = ('localhost', 12345)
    ch = Channel(chan)
    try:
        c = await ch.connect(authkey=syncword.encode())
    except AttributeError:
        raise IOError('Could not connect to the sync process, have you started sync.py?')
    async def send(uri):
        await c.send(uri)
        resp = await c.recv()
        #await c.close()
        print(resp, uri)
        return resp
    return send


class Locker:
    def __init__(self, send):
        self.send = send

    def _getQ(self):
        asdf = set()
        while 1:
            try:
                asdf.add(self.urls.get_nowait())
                print('oh boy')
            except Empty:
                break
        print('current queue', asdf)
        #print(id(self))
        return asdf
    
    def _setQ(self, uris):
        for uri in uris:
            print('putting uri', uri)
            self.urls.put(uri)
        print('done putting', uris, 'in queue')

    def start_uri(self, uri):
        val = run(self.send, 'add ' + uri)
        if val:
            return Response('URI Already running ' + uri)
        else:
            return

        print(self.lock, id(self.urls))
        with self.lock:
            print(self.lock, id(self.urls))
            uris = self._getQ()
            if uri in uris:
                print(uri, 'is already running')
                return Response('URI Already running')
            else:
                print('starting work for', uri)
                uris.add(uri)
            self._setQ(uris)

    def stop_uri(self, uri):
        run(self.send, 'del ' + uri)
        return
        #print(self.lock, id(self.urls))
        with self.lock:
            #print(self.lock, id(self.urls))
            uris = self._getQ()
            uris.discard(uri)
            print('completed work for', uri)
            self._setQ(uris)

#var canonical_url_obj=document.querySelector("link[rel=\\'canonical\\']");
#var canonical_url=canonical_url_obj?canonical_url_obj.href:null;
#var doi_obj=document.querySelector("meta[name=\\'DC.Identifier\\']");
#var doi=doi_obj?doi_obj.content:null;
#var sd_doi_obj=document.querySelector('a[class=\\'doi\\']');
#var sd_doi=sd_doi_obj?sd_doi_obj.href:null;
#document.querySelector('meta[name=\'DOI\']')


bookmarklet_base = r"""
javascript:(function(){var xhr=new XMLHttpRequest();

var params='uri='+location.href+
'&head='+encodeURIComponent(document.head.innerHTML)+
'&body='+encodeURIComponent(document.body.innerHTML)+
'&data='+encodeURIComponent(document.body.innerText);

xhr.open('POST','%s/%s',true);
xhr.setRequestHeader('Content-type','application/x-www-form-urlencoded');
xhr.setRequestHeader('Access-Control-Allow-Origin','*');
xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: '+xhr.responseText)};
xhr.send(params)}());
"""

html_base = """<html>
<head>
<style>
h1 { font-family: Arial,sans-serif; color: #777; font-size: 36px; font-weight: normal }
body { font-family: verdana; margin:.75in }
</style>
<title>SciBot bookmarklet</title></head>
<body>
<h1>SciBot</h1>
<p>To install the bookmarklet, drag this link -- <a href="%s">SciBot %s</a> -- to your bookmarks bar.</p>
<p>If you need to copy/paste the bookmarklet's code into a bookmarklet, it's here:</p>
<code>%s</code>
</body>
</html>
"""

def bookmarklet_wrapper(request, endpoint):
    """ Return text of the SciBot bookmarklet """
    code = bookmarklet_base % (request.application_url.replace('http:', 'https:'), endpoint)
    bookmarklet = code.replace('"', '&quot;').replace('\n','')
    html = html_base % (bookmarklet, request.host.split('.', 1)[-1], code)
    r = Response(html)
    r.content_type = 'text/html'
    return r

def bookmarklet(request):
    return bookmarklet_wrapper(request, 'rrid')

def validatebookmarklet(request):
    return bookmarklet_wrapper(request, 'validaterrid')

Found = Tuple[str, str, str, str]
Finder = Callable[[str], Iterable[Found]]
Checker = Callable[[Found], bool]
Resolved = Tuple[str, int, str]
Resolver = Callable[[Found], Resolved]
Submitter = Callable[[Found, Resolved], Any] 
Processor = Callable[[str, str], Generator]

def make_find_check_resolve_submit(finder: Finder, notSubmittedCheck: Checker, resolver: Resolver, submitter: Submitter) -> Processor:
    def inner(text: str) -> Generator:
        for found in finder(text):
            print(found)
            if notSubmittedCheck(found):
                resolved = resolver(found)
                yield submitter(found, resolved)
    return inner
    
def process_POST_request(request):
    dict_ = urlparse.parse_qs(request.text)
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
    return target_uri, doi, head, body, text

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
        ('meta', 'property', 'og:url', 'content'),
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
 
def existing_tags(target_uri, h):#, doi, text, h):
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

def get_pmid(doi):  # TODO
    params={'idtype':'auto', 'format':'json', 'Ids':doi, 'convert-button':'Convert'}
    pj = requests.post('https://www.ncbi.nlm.nih.gov/pmc/pmctopmid/', params=params).json()
    print(pj)
    for rec in pj['records']:
        try:
            return 'PMID:' + rec['pmid']
        except KeyError:
            pass

def DOI(doi):
    return 'https://doi.org/' + doi

def PMID(pmid):
    return pmid.replace('PMID:', 'https://www.ncbi.nlm.nih.gov/pubmed/')

def annotate_doi_pmid(target_uri, doi, pmid, h, tags):  # TODO
    # need to check for existing ...
    doi_ = 'DOI:' + doi
    text_list = []
    tags_to_add = []
    if doi_ not in tags:
        text_list.append(DOI(doi))
        tags_to_add.append(doi_)
    if pmid and pmid not in tags:
        text_list.append(PMID(pmid))
        tags_to_add.append(pmid)
    if tags_to_add:
        r = h.create_annotation_with_target_using_only_text_quote(target_uri, text='\n'.join(text_list), tags=tags_to_add)
        print(r)
        print(r.text)
        return r

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

def rrid_resolver_xml(exact, found_rrids):
    print('\t' + exact)
    resolver_uri = 'https://scicrunch.org/resolver/%s.xml' % exact
    r = requests.get(resolver_uri)
    status_code = r.status_code
    xml = r.content
    print(status_code)
    found_rrids[exact] = status_code
    return xml, status_code, resolver_uri

def check_already_submitted(exact, exact_for_hypothesis, found_rrids, tags, unresolved_exacts):
    if exact in tags or exact_for_hypothesis in unresolved_exacts:
        print('\tskipping %s, already annotated' % exact)
        found_rrids[exact] = 'Already Annotated'
        return True

def submit_to_h(target_uri, found, resolved, h, found_rrids, existing):
    prefix, exact, exact_for_hypothesis, suffix = found
    xml, status_code, resolver_uri = resolved

    new_tags = []
    if exact in existing:
        new_tags.append('RRIDCUR:Duplicate')
    else:
        existing.append(exact)

    if status_code < 300:
        root = etree.fromstring(xml)
        if root.findall('error'):
            s = 'Resolver lookup failed.'
            s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
            r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact_for_hypothesis, suffix=suffix, text=s, tags=new_tags + ['RRIDCUR:Unresolved'])
            print('ERROR, rrid unresolved')
        else:
            data_elements = root.findall('data')[0]
            s = ''
            data_elements = [(e.find('name').text, e.find('value').text) for e in data_elements]  # these shouldn't duplicate
            citation = [(n, v) for n, v in  data_elements if n == 'Proper Citation']
            name = [(n, v) for n, v in  data_elements if n == 'Name']
            data_elements = citation + name + sorted([(n, v) for n, v in  data_elements if (n != 'Proper Citation' or n != 'Name') and v is not None])
            for name, value in data_elements:
                if (name == 'Reference' or name == 'Mentioned In Literature') and value is not None and value.startswith('<a class'):
                    if len(value) > 500:
                        continue  # nif-0000-30467 fix keep those pubmed links short!
                s += '<p>%s: %s</p>' % (name, value)
            s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
            r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact_for_hypothesis, suffix=suffix, text=s, tags=new_tags + [exact])
    elif status_code >= 500:
        s = 'Resolver lookup failed due to server error.'
        s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
    else:
        s = 'Resolver lookup failed.'
        s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
        r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact_for_hypothesis, suffix=suffix, text=s, tags=new_tags + ['RRIDCUR:Unresolved'])
    found_rrids[exact] = r.json()['links']['incontext']
    return r

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

def write_stdout(target_uri, doi, pmid, found_rrids, head, body, text, h):
    #print(target_uri)
    print('DOI:%s' % doi)
    print(pmid)

def write_log(target_uri, doi, pmid, found_rrids, head, body, text, h):
    now = datetime.now().isoformat()[0:19].replace(':','').replace('-','')
    frv = list(set(found_rrids.values()))
    if len(frv) == 1 and frv[0] == 'Already Annotated':
        head, body, text = None, None, None
    log = {'target_uri':target_uri,
           'group':h.group,
           'doi':doi,
           'pmid':pmid,
           'found_rrids':found_rrids,
           'count':len(found_rrids),
           'head':head,
           'body':body,
           'text':text,
          }
    fname = 'logs/' + 'rrid-%s.json' % now
    with open(fname, 'wt') as f:
        json.dump(log, f, sort_keys=True, indent=4)

def export(request):
    print('starting csv export')
    output_rows, DATE = export_impl()    
    data = StringIO()
    writer = csv.writer(data)
    writer.writerows(sorted(output_rows))

    r = Response(gzip.compress(data.getvalue().encode()))
    r.content_type = 'text/csv'
    r.headers.update({
        'Content-Disposition':'attachment;filename = RRID-data-%s.csv' % DATE,
        'Content-Encoding':'gzip'
        })

    return r

def export_json(request):
    print('starting json export')
    output_json, DATE = export_json_impl()    
    data = json.dumps(output_json, sort_keys=True, indent=4)

    r = Response(gzip.compress(data.encode()))
    r.content_type = 'application/json'
    r.headers.update({
        'Content-Encoding':'gzip'
        })

    return r

def main(local=False):#, lock=None, urls=None):

    from wsgiref.simple_server import make_server
    from pyramid.config import Configurator

    send = run(producer)
    URL_LOCK = Locker(send)

    def rrid(request):
        return rrid_wrapper(request, username, api_token, group, 'logs/rrid/')

    def validaterrid(request):
        return rrid_wrapper(request, username, api_token, group2, 'logs/validaterrid/')

    def rrid_wrapper(request, username, api_token, group, logloc):
        """ Receive an article, parse RRIDs, resolve them, create annotations, log results """
        h = HypothesisUtils(username=username, token=api_token, group=group)
        if  request.method == 'OPTIONS':
            return rrid_OPTIONS(request)
        elif request.method == 'POST':
            return rrid_POST(request, h, logloc)
        else:
            return Response(status_code=405)

    def rrid_OPTIONS(request):
        response = Response()
        request_headers = request.headers['Access-Control-Request-Headers'].lower()
        request_headers = re.findall('\w(?:[-\w]*\w)', request_headers)
        response_headers = ['access-control-allow-origin']
        for req_acoa_header in request_headers:
            if req_acoa_header not in response_headers:
                response_headers.append(req_acoa_header)
        response_headers = ','.join(response_headers)
        response.headers.update({
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': '%s' % response_headers
            })
        response.status_int = 204
        return response

    def rrid_POST(request, h, logloc):
        target_uri, doi, head, body, text = process_POST_request(request)
        running = URL_LOCK.start_uri(target_uri)
        print(target_uri)
        if running:
            print('################# EARLY EXIT')
            return running
        cleaned_text = clean_text(text)
        tags, unresolved_exacts = existing_tags(target_uri, h)

        if doi:
            pmid = get_pmid(doi)
            annotate_doi_pmid(target_uri, doi, pmid, h, tags)
        else:
            pmid = None

        found_rrids = {}
        existing = []

        finder = find_rrids

        def checker(found):
            prefix, exact, exact_for_hypothesis, suffix = found
            return not check_already_submitted(exact, exact_for_hypothesis, found_rrids, tags, unresolved_exacts)

        def resolver(found):
            prefix, exact, exact_for_hypothesis, suffix = found
            return rrid_resolver_xml(exact, found_rrids)

        def submitter(found, resolved):
            return submit_to_h(target_uri, found, resolved, h, found_rrids, existing)

        processText = make_find_check_resolve_submit(finder, checker, resolver, submitter)

        responses = list(processText(cleaned_text))

        results = ', '.join(found_rrids.keys())
        write_stdout(target_uri, doi, pmid, found_rrids, head, body, text, h)
        write_log(target_uri, doi, pmid, found_rrids, head, body, text, h)

        r = Response(results)
        r.content_type = 'text/plain'
        r.headers.update({
            'Access-Control-Allow-Origin':'*',
        })

        URL_LOCK.stop_uri(target_uri)
        return r

    config = Configurator()

    config.add_route('rrid', '/rrid')
    config.add_view(rrid, route_name='rrid')

    config.add_route('validaterrid', 'validaterrid')
    config.add_view(validaterrid, route_name='validaterrid')

    config.add_route('bookmarklet', '/bookmarklet')
    config.add_view(bookmarklet, route_name='bookmarklet')

    config.add_route('validatebookmarklet', '/validatebookmarklet')
    config.add_view(validatebookmarklet, route_name='validatebookmarklet')

    config.add_route('export', '/export')
    config.add_view(export, route_name='export')

    config.add_route('export.json', '/export.json')
    config.add_view(export_json, route_name='export.json')

    app = config.make_wsgi_app()
    if not local:
        return app
    else:
        print('host: %s, port %s' % ( host, port ))
        server = make_server(host, port, app)
        # openssl req -new -x509 -keyout scibot-self-sign-temp.pem -out scibot-self-sign-temp.pem -days 365 -nodes
        #server.socket = ssl.wrap_socket(server.socket, keyfile='/etc/letsencrypt/live/scibot.scicrunch.io/privkey.pem', certfile='/etc/letsencrypt/live/scibot.scicrunch.io/fullchain.pem', server_side=True)
        server.socket = ssl.wrap_socket(server.socket, keyfile='/mnt/str/tom/files/certs/scibot_test/tmp-nginx.key', certfile='/mnt/str/tom/files/certs/scibot_test/tmp-nginx.crt', server_side=True)
        server.serve_forever()

def _main(local=False):
    from time import sleep
    from curio import Channel, run
    from pyramid.config import Configurator

    async def producer():
        chan = ('localhost', 12345)
        ch = Channel(chan)
        c = await ch.connect(authkey=b'hello')
        async def send(uri):
            await c.send(uri)
            resp = await c.recv()
            #await c.close()
            print(resp, uri)
            return resp
        return send

    send = run(producer)
    print('we are ready')  # for some reason this only runs once
    uri1 = 'http://testing.org/1'
    uri2 = 'http://testing.org/2'
    def testing(request):
        val = run(send, 'add ' + uri1)
        print(val)
        if val:
            print('### EARLY EXIT')
            return Response('ALREADY RUNNING 1')
        else:
            sleep(2)
            val = run(send, 'del ' + uri1)
        return Response('aaaaaaaaaaa')

    def testing2(request):
        val = run(send, 'add ' + uri2)
        print(val)
        if val:
            print('### EARLY EXIT')
            return Response('ALREADY RUNNING 2')
        else:
            sleep(2)
            val = run(send, 'del ' + uri2)
        return Response('bbbbbbbbbbb')

    config = Configurator()
    config.add_route('testing', '/testing')
    config.add_view(testing, route_name='testing')
    config.add_route('testing2', '/testing2')
    config.add_view(testing2, route_name='testing2')
    return config.make_wsgi_app()

if __name__ == '__main__':
    main(local=True)
