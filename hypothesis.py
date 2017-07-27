#!/usr/bin/env python3
from __future__ import print_function
import json
import requests
import traceback
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

class HypothesisUtils:
    """ services for authenticating, searching, creating annotations """
    def __init__(self, username=None, token=None, limit=None, max_results=None, domain=None, group=None):
        if domain is None:
            self.domain = 'hypothes.is'
        else:
            self.domain = domain
        if username is not None:
            self.username = username
        if token is not None:
            self.token = token
        self.app_url = 'https://%s/app' % self.domain
        self.api_url = 'https://%s/api' % self.domain
        self.query_url_template = 'https://%s/api/search?{query}' % self.domain
        self.group = group if group is not None else '__world__'
        self.single_page_limit = 200 if limit is None else limit  # per-page, the api honors limit= up to (currently) 200
        self.multi_page_limit = 200 if max_results is None else max_results  # limit for paginated results
        self.permissions = {
                "read": ['group:' + self.group],
                "update": ['acct:' + self.username + '@hypothes.is'],
                "delete": ['acct:' + self.username + '@hypothes.is'],
                "admin":  ['acct:' + self.username + '@hypothes.is']
                }
        self.ssl_retry = 0

    def authenticated_api_query(self, query_url=None):
        try:
           headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json;charset=utf-8' }
           r = requests.get(query_url, headers=headers)
           obj = json.loads(r.text)
           return obj
        except requests.exceptions.SSLError as e:
            if self.ssl_retry < 5:
                self.ssl_retry += 1
                print('Ssl error at level', self.ssl_retry, 'retrying....')
                return self.authenticated_api_query(query_url)
            else:
                self.ssl_retry = 0
                print(e)
                print(traceback.print_exc())
                return {'ERROR':True, 'rows':tuple()}
        except BaseException as e:
            print(e)
            #print('Request, status code:', r.status_code)  # this causes more errors...
            print(traceback.print_exc())
            return {'ERROR':True, 'rows':tuple()}

    def make_annotation_payload_with_target_using_only_text_quote(self, url, prefix, exact, suffix, text, tags):
        """Create JSON payload for API call."""
        if tags == None:
            tags = []
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
               exact=None, suffix=None, text=None, tags=None, tag_prefix=None):
        """Call API with token and payload, create annotation (using only text quote)"""
        payload = self.make_annotation_payload_with_target_using_only_text_quote(url, prefix, exact, suffix, text, tags)
        try:
            r = self.post_annotation(payload)
        except:
            print(traceback.print_exc())
            r = None  # if we get here someone probably ran the bookmarklet from firefox or the like
        return r

    def post_annotation(self, payload):
        headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json;charset=utf-8' }
        data = json.dumps(payload, ensure_ascii=False)
        r = requests.post(self.api_url + '/annotations', headers=headers, data=data.encode('utf-8'))
        return r

    def search_all(self, params={}):
        """Call search API with pagination, return rows """
        while True:
            obj = self.search(params)
            rows = obj['rows']
            row_count = len(rows)
            if 'replies' in obj:
                rows += obj['replies']
            params['offset'] += row_count
            if params['offset'] > self.multi_page_limit:
                break
            if len(rows) is 0:
                break
            for row in rows:
                yield row

    def search(self, params={}):
        """ Call search API, return a dict """
        if 'offset' not in params:
            params['offset'] = 0
        if 'limit' not in params or 'limit' in params and params['limit'] is None:
            params['limit'] = self.single_page_limit
        query_url = self.query_url_template.format(query=urlencode(params, True))
        obj = self.authenticated_api_query(query_url)
        return obj

class HypothesisAnnotation:
    """Encapsulate one row of a Hypothesis API search."""
    def __init__(self, row):
        self.type = None
        self.id = row['id']
        self.updated = row['updated'][0:19]
        self.user = row['user'].replace('acct:','').replace('@hypothes.is','')

        if 'uri' in row:    # should it ever not?
            self.uri = row['uri']
        else:
             self.uri = "no uri field for %s" % self.id
        self.uri = self.uri.replace('https://via.hypothes.is/h/','').replace('https://via.hypothes.is/','')

        if self.uri.startswith('urn:x-pdf') and 'document' in row:
            if 'link' in row['document']:
                self.links = row['document']['link']
                for link in self.links:
                    self.uri = link['href']
                    if self.uri.encode('utf-8').startswith(b'urn:') == False:
                        break
            if self.uri.encode('utf-8').startswith(b'urn:') and 'filename' in row['document']:
                self.uri = row['document']['filename']

        if 'document' in row and 'title' in row['document']:
            t = row['document']['title']
            if isinstance(t, list) and len(t):
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
        if 'tags' in row and row['tags'] is not None:
            self.tags = row['tags']
            if isinstance(self.tags, list):
                self.tags = [t.strip() for t in self.tags]

        self.text = ''
        if 'text' in row:
            self.text = row['text']

        self.references = []
        if 'references' in row:
            self.type = 'reply'
            self.references = row['references']

        self.target = []
        if 'target' in row:
            self.target = row['target']

        self.is_page_note = False
        try:
            if self.references == [] and self.target is not None and len(self.target) and isinstance(self.target,list) and 'selector' not in self.target[0]:
                self.is_page_note = True
                self.type = 'pagenote'
        except:
            traceback.print_exc()
        if 'document' in row and 'link' in row['document']:
            self.links = row['document']['link']
            if not isinstance(self.links, list):
                self.links = [{'href':self.links}]
        else:
            self.links = []

        self.start = self.end = self.prefix = self.exact = self.suffix = None
        try:
            if isinstance(self.target,list) and len(self.target) and 'selector' in self.target[0]:
                self.type = 'annotation'
                selectors = self.target[0]['selector']
                for selector in selectors:
                    if 'type' in selector and selector['type'] == 'TextQuoteSelector':
                        try:
                            self.prefix = selector['prefix']
                            self.exact = selector['exact']
                            self.suffix = selector['suffix']
                        except:
                            traceback.print_exc()
                    if 'type' in selector and selector['type'] == 'TextPositionSelector' and 'start' in selector:
                        self.start = selector['start']
                        self.end = selector['end']
                    if 'type' in selector and selector['type'] == 'FragmentSelector' and 'value' in selector:
                        self.fragment_selector = selector['value']

        except:
            print(traceback.format_exc())

    def __eq__(self, other):
        # text and tags can change, if exact changes then the id will also change
        return self.id == other.id and self.text == other.text and set(self.tags) == set(other.tags)

    def __hash__(self):
        return hash(self.text + self.id)

