#!/usr/bin/env python3
import json, requests, re, traceback, pyramid
try:
    import urlparse
except ImportError:  # python3
    from urllib import parse as urlparse
from datetime import datetime
from lxml import etree
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

host = 'localhost'
port = 8080
host_port = 'http://' + host + ':' + str(port)
username = 'USERNAME'  # Hypothesis account
password = 'PASSWORD'

class HypothesisUtils:
    """ services for authenticating, searching, creating annotations """
    def __init__(self, username='username', password=None, limit=None, max_results=None, domain=None):
        if domain is None:
            self.domain = 'hypothes.is'
        else:
            self.domain = domain
        self.app_url = 'https://%s/app' % self.domain
        self.api_url = 'https://%s/api' % self.domain
        self.query_url = 'https://%s/api/search?{query}' % self.domain
        self.username = username
        self.password = password
        self.permissions = {
                "read": ["group:__world__"],
                "update": ['acct:' + self.username + '@hypothes.is'],
                "delete": ['acct:' + self.username + '@hypothes.is'],
                "admin":  ['acct:' + self.username + '@hypothes.is']
                }

    def login(self):
        """Request an assertion, exchange it for an auth token."""
        # https://github.com/rdhyee/hypothesisapi
        r = requests.get(self.app_url)
        cookies = r.cookies
        payload = {"username":self.username,"password":self.password}
        self.csrf_token = cookies['XSRF-TOKEN']
        data = json.dumps(payload)
        headers = {'content-type':'application/json;charset=UTF-8', 'x-csrf-token': self.csrf_token}
        r = requests.post(url=self.app_url + "?__formid__=login", data=data, cookies=cookies, headers=headers)
        url = self.api_url + "/token?" + urlencode({'assertion':self.csrf_token})
        r = (requests.get(url=url,
                         cookies=cookies, headers=headers))
        self.token = r.content

    def make_annotation_payload_with_target_using_only_text_quote(self, url, prefix, exact, suffix, text, tags):
        """Create JSON payload for API call."""
        if tags == None:
            tags = []
        url = url.rstrip('//')
        payload = {
            "uri": url,
            "user": 'acct:' + self.username + '@hypothes.is',
            "permissions": self.permissions,
            "target": 
            [{
                "scope": [url],
                "selector": 
                    [{
                        "type": "TextQuoteSelector", 
                        "prefix": prefix,
                        "exact": exact,
                        "suffix": suffix
                        },]
                }], 
            "tags": tags,
            "text": text
        }
        return payload

    def create_annotation_with_target_using_only_text_quote(self, url=None, prefix=None, 
               exact=None, suffix=None, text=None, tags=None):
        """Call API with token and payload, create annotation (using only text quote)"""
        tags = ['RRID:' + exact]
        payload = self.make_annotation_payload_with_target_using_only_text_quote(url, prefix, exact, suffix, text, tags)
        try:
            r = self.post_annotation(payload)
        except:
            print(traceback.print_exc())
        return r

    def post_annotation(self, payload):
        headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json;charset=utf-8' }
        data = json.dumps(payload, ensure_ascii=False)
        r = requests.post(self.api_url + '/annotations', headers=headers, data=data.encode('utf-8'))
        return r

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

    # http://www.jneurosci.org/content/34/24/8151.full 
    target_uri = urlparse.parse_qs(request.body)[b'uri'][0].decode('utf-8')
    api_query = 'https://hypothes.is/api/search?limit=200&uri=' + target_uri
    s = requests.get(api_query).text#.decode('utf-8')
    rows = json.loads(s)['rows']
    tags = [row['tags'][0] for row in rows]
    html = urlparse.parse_qs(request.body)[b'data'][0].decode('utf-8')
    print(target_uri)
    h = HypothesisUtils(username=username, password=password)
    h.login()
    found_rrids = {}
    try:
        matches = re.findall('(.{10}?)(RRID:\s*)([_\w\-:]+)([^\w].{10}?)', html)
        for match in matches:
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
            root = etree.fromstring(xml)
            data_elements = root.findall('data')[0]
            s = ''
            for data_element in data_elements:
                name = data_element.find('name').text
                value =data_element.find('value').text
                s += '<p>%s: %s</p>' % (name, value)
            s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
            r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact, suffix=suffix, text=s)
    except:
        print('error: %' % exact)
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
        with open(fname, 'wt') as f:
            f.write(s)
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


