import json, requests, re, traceback, pyramid, urlparse, types
from datetime import datetime
from lxml import etree
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

class HypothesisUtils:
    """ services for authenticating, searching, creating annotations """
    def __init__(self, username='username', password=None, limit=None, max_results=None, domain=None, group=None):
        if domain is None:
            self.domain = 'hypothes.is'
        else:
            self.domain = domain
        self.app_url = 'https://%s/app' % self.domain
        self.api_url = 'https://%s/api' % self.domain
        self.query_url = 'https://%s/api/search?{query}' % self.domain
        self.username = username
        self.password = password
        self.group = group if group is not None else '__world__'
        self.single_page_limit = 200 if limit is None else limit  # per-page, the api honors limit= up to (currently) 200
        self.multi_page_limit = 200 if max_results is None else max_results  # limit for paginated results
        self.permissions = {
                "read": ['group:' + self.group],
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

    def authenticated_api_query(self, url=None):
        try:
           headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json;charset=utf-8' }
           r = requests.get(url, headers=headers)
           obj = json.loads(r.text)
           return obj
        except:
            print traceback.print_exc()

    def make_annotation_payload_with_target_using_only_text_quote(self, url, prefix, exact, suffix, text, tags):
        """Create JSON payload for API call."""
        if tags == None:
            tags = []
        url = url.rstrip('//')
        payload = {
            "uri": url,
            "user": 'acct:' + self.username + '@hypothes.is',
            "permissions": self.permissions,
            "group": self.group,
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
            print traceback.print_exc()
        return r

    def post_annotation(self, payload):
        headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json;charset=utf-8' }
        data = json.dumps(payload, ensure_ascii=False)
        r = requests.post(self.api_url + '/annotations', headers=headers, data=data.encode('utf-8'))
        return r

    def search_all(self, params={}):
        """Call search API with pagination, return rows """
        params['offset'] = 0
        params['limit'] = self.single_page_limit
        while True:
            h_url = self.query_url.format(query=urlencode(params, True))
            obj = self.authenticated_api_call(h_url)
            rows = obj['rows']
            row_count = len(rows)
            if obj.has_key('replies'):
               rows += obj['replies']
            params['offset'] += row_count
            if params['offset'] > self.multi_page_limit:
                break
            if len(rows) is 0:
                break
            for row in rows:
                yield row

    def authenticated_api_call(self, url=None):
        try:
           self.login()
           headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json;charset=utf-8' }
           r = requests.get(url, headers=headers)
           obj = json.loads(r.text.decode('utf-8'))
           return obj
        except:
            print traceback.print_exc()

    def make_annotation_payload_with_target_using_only_text_quote(self, url, prefix, exact, suffix, text, tags):
        """Create JSON payload for API call."""
        payload = {
            "uri": url,
            "user": 'acct:' + self.username + '@hypothes.is',
            "permissions": self.permissions,
            #"document": {
            #    "link": [ { "href": url } ]
            #    },
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

class HypothesisAnnotation:
    """Encapsulate one row of a Hypothesis API search."""   
    def __init__(self, row):
        self.type = None
        self.id = row['id']
        self.updated = row['updated'][0:19]
        self.user = row['user'].replace('acct:','').replace('@hypothes.is','')

        if row.has_key('uri'):    # should it ever not?
            self.uri = row['uri']
        else:
             self.uri = "no uri field for %s" % self.id
        self.uri = self.uri.replace('https://via.hypothes.is/h/','').replace('https://via.hypothes.is/','')

        if self.uri.startswith('urn:x-pdf') and row.has_key('document'):
            if row['document'].has_key('link'):
                self.links = row['document']['link']
                for link in self.links:
                    self.uri = link['href']
                    if self.uri.encode('utf-8').startswith('urn:') == False:
                        break
            if self.uri.encode('utf-8').startswith('urn:') and row['document'].has_key('filename'):
                self.uri = row['document']['filename']

        if row.has_key('document') and row['document'].has_key('title'):
            t = row['document']['title']
            if isinstance(t, types.ListType) and len(t):
                self.doc_title = t[0]
            else:
                self.doc_title = t
        else:
            self.doc_title = self.uri
        if self.doc_title is None:
            self.doc_title = ''
        self.doc_title = self.doc_title.replace('"',"'")
        if self.doc_title == '': self.doc_title = 'untitled'

        self.tags = []
        if row.has_key('tags') and row['tags'] is not None:
            self.tags = row['tags']
            if isinstance(self.tags, types.ListType):
                self.tags = [t.strip() for t in self.tags]

        self.text = ''
        if row.has_key('text'):
            self.text = row['text']

        self.references = []
        if row.has_key('references'):
            self.type = 'reply'
            self.references = row['references']

        self.target = []
        if row.has_key('target'):
            self.target = row['target']

        self.is_page_note = False
        try:
            if self.references == [] and self.target is not None and len(self.target) and isinstance(self.target,list) and self.target[0].has_key('selector') == False:
                self.is_page_note = True
                self.type = 'pagenote'
        except:
            traceback.print_exc()
        if row.has_key('document') and row['document'].has_key('link'):
            self.links = row['document']['link']
            if not isinstance(self.links, types.ListType):
                self.links = [{'href':self.links}]
        else:
            self.links = []

        self.start = self.end = self.prefix = self.exact = self.suffix = None
        try:
            if isinstance(self.target,list) and len(self.target) and self.target[0].has_key('selector'):
                self.type = 'annotation'
                selectors = self.target[0]['selector']
                for selector in selectors:
                    if selector.has_key('type') and selector['type'] == 'TextQuoteSelector':
                        try:
                            self.prefix = selector['prefix']
                            self.exact = selector['exact']
                            self.suffix = selector['suffix']
                        except:
                            traceback.print_exc()
                    if selector.has_key('type') and selector['type'] == 'TextPositionSelector' and selector.has_key('start'):
                        self.start = selector['start']
                        self.end = selector['end']
                    if selector.has_key('type') and selector['type'] == 'FragmentSelector' and selector.has_key('value'):
                        self.fragment_selector = selector['value']

        except:
            print traceback.format_exc()

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

    target_uri = urlparse.parse_qs(request.body)['uri'][0]
    api_query = 'https://hypothes.is/api/search?limit=200&uri=' + target_uri
    obj = h.authenticated_api_query(api_query)
    rows = obj['rows']
    tags = set()
    for row in rows:
        for tag in row['tags']:
            if tag.startswith('RRID'):
                tags.add(tag)
    html = urlparse.parse_qs(request.body)['data'][0].decode('utf-8')
    print target_uri

    found_rrids = {}
    try:
        matches = re.findall('(.{10}?)(RRID:\s*)([_\w\-:]+)([^\w].{10}?)', html)
        for match in matches:
            prefix = match[0]
            exact = match[2]
            if 'RRID:'+exact in tags:
                print 'skipping %s, already annotated' % exact
                continue
            found_rrids[exact] = None
            suffix = match[3]
            print '\t' + exact
            resolver_uri = 'https://scicrunch.org/resolver/%s.xml' % exact
            r = requests.get(resolver_uri)
            print r.status_code
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
        print 'error: %' % exact
        print traceback.print_exc()

    results = ', '.join(found_rrids.keys())
    r = Response(results)
    r.content_type = 'text/plain'
    r.headers.update({
        'Access-Control-Allow-Origin': '*'
        })

    try:
        now = datetime.now().isoformat()[0:19].replace(':','').replace('-','')
        fname = 'rrid-%s.log' % now
        f = open(fname,'w')
        s = 'URL: %s\n\nResults: %s\n\nCount: %s\n\nText:\n\n%s' % ( target_uri, results, len(found_rrids), html ) 
        f.write(s.encode('utf-8'))
        f.close()
    except:
        print traceback.print_exc()

    return r

if __name__ == '__main__':

    host = 'HOST'
    port = PORT
    host_port = 'http://' + host + ':' + str(port)
    username = 'USERNAME'  # Hypothesis account
    password = 'PASSWORD'
    group = 'GROUP'

    from wsgiref.simple_server import make_server
    from pyramid.config import Configurator
    from pyramid.response import Response

    config = Configurator()

    config.add_route('rrid', '/rrid')
    config.add_view(rrid, route_name='rrid')

    config.add_route('bookmarklet', '/bookmarklet')
    config.add_view(bookmarklet, route_name='bookmarklet')

    app = config.make_wsgi_app()
    print 'host: %s, port %s' % ( host, port )
    server = make_server(host, port, app)
    server.serve_forever()


