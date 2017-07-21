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
from lxml import etree
from curio import Channel, run
from pyramid.response import Response
from hypothesis import HypothesisUtils
from export import export_impl, export_json_impl
from IPython import embed

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

# synchronization setup
async def producer():
    chan = ('localhost', 12345)
    ch = Channel(chan)
    c = await ch.connect(authkey=syncword.encode())
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

send = run(producer)
URL_LOCK = Locker(send)

def bookmarklet(request):
    """ Return text of the RRID bookmarklet """
    text = """javascript:(function(){var xhr=new XMLHttpRequest();var params='uri='+location.href+'&data='+encodeURIComponent(document.body.innerText);xhr.open('POST','%s/rrid',true);xhr.setRequestHeader("Content-type","application/x-www-form-urlencoded");xhr.setRequestHeader("Access-Control-Allow-Origin","*");xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: '+xhr.responseText)};xhr.send(params)}());""" % request.application_url.replace('http:','https:')  # pyramid is blind to ssl...
    text = text.replace('"',"'")
    html = """<html>
    <head>
    <style>
    body { font-family: verdana; margin:.75in }
    </style>
    <title>rrid bookmarklet</title></head>
    <body>
    <p>To install the bookmarklet, drag this link -- <a href="%s">rrid</a> -- to your bookmarks bar.</p>
    <p>If you need to copy/paste the bookmarklet's code into a bookmarklet, it's here:</p>
    <p>%s</p>
    </body>
    </html>
    """ % ( text, text )
    r = Response(html)
    r.content_type = 'text/html'
    return r

def validatebookmarklet(request):
    """ Return text of the RRID bookmarklet """
    text = """javascript:(function(){var xhr=new XMLHttpRequest();var params='uri='+location.href+'&data='+encodeURIComponent(document.body.innerText);xhr.open('POST','%s/validaterrid',true);xhr.setRequestHeader("Content-type","application/x-www-form-urlencoded");xhr.setRequestHeader("Access-Control-Allow-Origin","*");xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: '+xhr.responseText)};xhr.send(params)}());""" % request.application_url.replace('http:','https:')  # pyramid is blind to ssl...
    text = text.replace('"',"'")
    html = """<html>
    <head>
    <style>
    body { font-family: verdana; margin:.75in }
    </style>
    <title>validaterrid bookmarklet</title></head>
    <body>
    <p>To install the bookmarklet, drag this link -- <a href="%s">validaterrid</a> -- to your bookmarks bar.</p>
    <p>If you need to copy/paste the bookmarklet's code into a bookmarklet, it's here:</p>
    <p>%s</p>
    </body>
    </html>
    """ % ( text, text )
    r = Response(html)
    r.content_type = 'text/html'
    return r

def rrid(request):
    return rrid_wrapper(request, username, api_token, group, 'logs/rrid/')

def validaterrid(request):
    return rrid_wrapper(request, username, api_token, group2, 'logs/validaterrid/')

def rrid_wrapper(request, username, api_token, group, logloc):
    """ Receive an article, parse RRIDs, resolve them, create annotations, log results """
    if  request.method == 'OPTIONS':
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

    h = HypothesisUtils(username=username, token=api_token, group=group)

    target_uri = urlparse.parse_qs(request.text)['uri'][0]
    existing = URL_LOCK.start_uri(target_uri)
    if existing:
        print('################# EARLY EXIT')
        return existing

    params = { 'limit':200, 'uri':target_uri }
    query_url = h.query_url_template.format(query=urlencode(params, True))
    obj = h.authenticated_api_query(query_url)
    rows = obj['rows']
    tags = set()
    for row in rows:
        if row['group'] != h.group:  # api query returns unwanted groups
            continue
        elif row['user'] != 'acct:' + h.username + '@hypothes.is':
            continue
        for tag in row['tags']:
            if tag.startswith('RRID'):
                tags.add(tag)
    html = urlparse.parse_qs(request.text)['data'][0]

    # cleanup the html
    text = html.replace('–','-')
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
    replace = r'\1_\2\3'
    def make_cartesian_product(prefix, suffix=r'(\d+)'):
        return [(prefix + mid + suffix + tail, replace) for mid in mids]

    fixes = []
    prefixes_digit = [r'(%s)' % _ for _ in ('AB', 'SCR', 'MGI')]
    for p in prefixes_digit:
        fixes.extend(make_cartesian_product(p))
    fixes.extend(make_cartesian_product(r'(CVCL)', r'(\w{0,1}\d+)'))
    fixes.append((r'\(RRID\):', r'RRID:'))

    for f, r in fixes:
        text = re.sub(f, r, text)

    found_rrids = {}
    try:
        matches = re.findall('(.{0,32})(RRID(:|\)*,*)[ \t]*)(\w+[_\-:]+[\w\-]+)([^\w].{0,32})', text)
        existing = []
        for match in matches:
            print(match)
            prefix = match[0]
            exact = 'RRID:' + match[3]
            if exact in tags:
                print('skipping %s, already annotated' % exact)
                continue

            new_tags = []
            if exact in existing:
                new_tags.append('RRIDCUR:Duplicate')
            else:
                existing.append(exact)

            found_rrids[exact] = None
            suffix = match[4]
            print('\t' + exact)
            resolver_uri = 'https://scicrunch.org/resolver/%s.xml' % exact
            r = requests.get(resolver_uri)
            print(r.status_code)
            xml = r.content
            found_rrids[exact] = r.status_code
            if r.status_code < 300:
                root = etree.fromstring(xml)
                if root.findall('error'):
                    s = 'Resolver lookup failed.'
                    s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
                    r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact, suffix=suffix, text=s, tags=new_tags + ['RRIDCUR:Unresolved'])
                    print('ERROR')
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
                    r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact, suffix=suffix, text=s, tags=new_tags + [exact])
            elif r.status_code >= 500:
                s = 'Resolver lookup failed due to server error.'
                s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
            else:
                s = 'Resolver lookup failed.'
                s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
                r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact, suffix=suffix, text=s, tags=new_tags + ['RRIDCUR:Unresolved'])
    except:
        print(traceback.print_exc())

    results = ', '.join(found_rrids.keys())
    r = Response(results)
    r.content_type = 'text/plain'
    r.headers.update({
        'Access-Control-Allow-Origin': '*'
        })

    try:
        now = datetime.now().isoformat()[0:19].replace(':','').replace('-','')
        fname = logloc + 'rrid-%s.log' % now
        s = 'URL: %s\n\nResults: %s\n\nCount: %s\n\nText:\n\n%s' % ( target_uri, results, len(found_rrids), html ) 
        with open(fname, 'wb') as f:
            f.write(s.encode('utf-8'))
    except:
        print(traceback.print_exc())

    URL_LOCK.stop_uri(target_uri)
    #embed()
    return r

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
