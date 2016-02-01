#!/usr/bin/env python3
from __future__ import print_function
import requests, re, traceback, pyramid
try:
    import urlparse
except ImportError:  # python3
    from urllib import parse as urlparse
from os import environ
from datetime import datetime
from lxml import etree
from hypothesis import HypothesisUtils

username = environ.get('RRIDBOT_USERNAME', 'USERNAME')  # Hypothesis account
password = environ.get('RRIDBOT_PASSWORD', 'PASSWORD')
group = environ.get('RRIDBOT_GROUP', '__world__')
print(username, group)  # sanity check

prod_username = 'scibot'  # nasty hardcode

if username == prod_username:
    host = '0.0.0.0'
    port = 80

else: 
    print('no login detected, running on localhost only')
    host = 'localhost'
    port = 8080

host_port = 'http://' + host + ':' + str(port)

def bookmarklet(request):
    """ Return text of the RRID bookmarklet """
    text = """javascript:(function(){var xhr=new XMLHttpRequest();var params='uri='+location.href+'&data='+encodeURIComponent(document.body.innerText);xhr.open('POST','%s/rrid',true);xhr.setRequestHeader("Content-type","application/x-www-form-urlencoded");xhr.setRequestHeader("Access-Control-Allow-Origin","*");xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: '+xhr.responseText)};xhr.send(params)}());""" % request.application_url
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

def rrid(request):   
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

    h = HypothesisUtils(username=username, password=password, group=group)
    h.login()

    target_uri = urlparse.parse_qs(request.text)['uri'][0]
    api_query = 'https://hypothes.is/api/search?limit=200&uri=' + target_uri
    obj = h.authenticated_api_query(api_query)
    rows = obj['rows']
    tags = set()
    for row in rows:
        if row['group'] != group:  # api query returns unwanted groups
            continue
        for tag in row['tags']:
            if tag.startswith('RRID'):
                tags.add(tag)
    html = urlparse.parse_qs(request.text)['data'][0]
    print(target_uri)

    found_rrids = {}
    try:
        matches = re.findall('(.{0,10})(RRID:\s*)([_\w\-:]+)([^\w].{0,10})', html.replace('–','-'))
        for match in matches:
            print(match)
            prefix = match[0]
            exact = match[2]
            if 'RRID:'+exact in tags:
                print('skipping %s, already annotated' % exact)
                continue
            found_rrids[exact] = None
            suffix = match[3]
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
                    r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact, suffix=suffix, text=s, tags=['RRID:Unresolved'])
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
                    print(s)
                    s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
                    r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact, suffix=suffix, text=s)
            else:
                s = 'Resolver lookup failed.'
                r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact, suffix=suffix, text=s, tags={'RRID:Unresolved'})
    except:
        print('error: %s' % exact)
        print(traceback.print_exc())

    results = ', '.join(found_rrids.keys())
    r = Response(results)
    r.content_type = 'text/plain'
    r.headers.update({
        'Access-Control-Allow-Origin': '*'
        })

    try:
        now = datetime.now().isoformat()[0:19].replace(':','').replace('-','')
        fname = 'rrid-%s.log' % now
        s = 'URL: %s\n\nResults: %s\n\nCount: %s\n\nText:\n\n%s' % ( target_uri, results, len(found_rrids), html ) 
        with open(fname, 'wb') as f:
            f.write(s.encode('utf-8'))
    except:
        print(traceback.print_exc())

    return r

if __name__ == '__main__':

    from wsgiref.simple_server import make_server
    from pyramid.config import Configurator
    from pyramid.response import Response

    config = Configurator()

    config.add_route('rrid', '/rrid')
    config.add_view(rrid, route_name='rrid')

    config.add_route('bookmarklet', '/bookmarklet')
    config.add_view(bookmarklet, route_name='bookmarklet')

    app = config.make_wsgi_app()
    print('host: %s, port %s' % ( host, port ))
    server = make_server(host, port, app)
    server.serve_forever()

