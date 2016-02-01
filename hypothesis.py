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
        self.token = r.content.decode('utf-8')

    def authenticated_api_query(self, url=None):
        try:
           headers = {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json;charset=utf-8' }
           r = requests.get(url, headers=headers)
           obj = json.loads(r.text)
           return obj
        except:
            print(traceback.print_exc())

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
        tags = [] if tags is None else tags
        tags += ['RRID:' + exact]
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

