#!/usr/bin/env python3
"""SciBot server implementation

Usage:
    bookmarklet [options]

Options:
    -s --sync-port=PORT         the port that the sync services is running on
"""

import re
import csv
import ssl
import gzip
import json
import asyncio
from io import StringIO
from typing import Callable, Iterable, Tuple, Any, Generator
from pathlib import Path
from datetime import datetime
from curio import run
from curio.channel import AuthenticationError
from flask import Flask, request, abort, current_app
from hyputils.hypothesis import HypothesisUtils
from scibot.config import source_log_location
from scibot.utils import log
from scibot.export import export_impl, export_json_impl
from pyontutils.utils import Async, deferred

try:
    from scibot.workflow import curatorTags
except ImportError:
    # FIXME don't want a hard rdflib dependency here
    curatorTags = lambda : []

from IPython import embed


# logging

def write_stdout(target_uri, document, doi, pmid, found_rrids, head, body, text, h):
    log.info(f'DOI:{doi}')
    log.info(pmid)


def write_log(target_uri, document, doi, pmid, found_rrids, head, body, text, h):
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
           'document': document,
          }
    fname = Path(source_log_location, f'rrid-{now}.json')
    with open(fname.as_posix(), 'wt') as f:
        json.dump(log, f, sort_keys=True, indent=4)

# types

Found = Tuple[str, str, str, str]
Finder = Callable[[str], Iterable[Found]]
Checker = Callable[[Found], bool]
Resolved = Tuple[str, int, str]
Resolver = Callable[[Found], Resolved]
Submitter = Callable[[Found, Resolved], Any]
Processor = Callable[[str, str], Generator]

# bookmarklet endpoint

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
    normalized = 'https://' + request.host
    code = bookmarklet_base % (normalized, endpoint)
    bookmarklet = code.replace('"', '&quot;').replace('\n','')
    html = html_base % (bookmarklet, request.host.split('.', 1)[-1], code)
    return html


# rrid endpoint

from scibot.extract import process_POST_request, find_rrids as finder
from scibot.check import check_already_submitted
from scibot.services import existing_tags, get_pmid, rrid_resolver_xml
from scibot.submit import annotate_doi_pmid, submit_to_h


def make_find_check_resolve_submit(finder: Finder, notSubmittedCheck: Checker,
                                   resolver: Resolver, submitter: Submitter) -> Processor:

    def async_inner(found):
        log.info(found)
        if notSubmittedCheck(found):
            resolved = resolver(found)
            yield submitter(found, resolved)

    def inner(text: str) -> Generator:
        while True:
            try:
                yield from Async(rate=5)(deferred(async_inner)(found) for found in finder(text))
                return
            except RuntimeError:
                asyncio.set_event_loop(current_app.config['loop'])

    return inner


def pmid_logic(doi, pmid_from_source, target_uri=None, document=None, h=None, tags=None):
    # TODO move the annotation of errors out of this
    if doi:
        pmid_from_doi = get_pmid(doi)
    else:
        pmid_from_doi = None

    if pmid_from_source and pmid_from_doi:
        if pmid_from_source == pmid_from_doi:
            pmid = pmid_from_source
        else:
            # TODO responses -> db
            # TODO tag for marking errors explicitly without the dashboard?
            r1 = annotate_doi_pmid(target_uri, document, None, pmid_from_doi, h, tags, 'ERROR\nPMID from DOI')
            r2 = annotate_doi_pmid(target_uri, document, None, pmid_from_source, h, tags, 'ERROR\nPMID from source')
            pmid = None
    elif pmid_from_source:
        pmid = pmid_from_source
    elif pmid_from_doi:
        pmid = pmid_from_doi
    else:
        pmid = None

    return pmid


def rrid_POST(request, h, logloc, URL_LOCK):
    (target_uri, document, doi, pmid_from_source,
     head, body, text, cleaned_text) = process_POST_request(request)
    running = URL_LOCK.start_uri(target_uri)
    log.info(target_uri)
    if running:
        log.info('################# EARLY EXIT')
        return 'URI Already running ' + target_uri

    try:
        tags, unresolved_exacts = existing_tags(target_uri, h)
        pmid = pmid_logic(doi, pmid_from_source, target_uri, document, h, tags)
        r = annotate_doi_pmid(target_uri, document, doi, pmid, h, tags)  # todo r -> db with responses

        # these values are defined up here as shared state that will be
        # mutated across multiple calls to checker, resolver, and submitter
        # this is a really bad design because it is not clear that processText
        # actually does this ... once again, python is best if you just use the
        # objects and give up any hope for an alternative approach, the way it
        # is done here also makes the scope where these values could be used
        # completely ambiguous and hard to understand/reason about

        found_rrids = {}
        existing = []
        existing_with_suffixes = []

        def checker(found):
            prefix, exact, exact_for_hypothesis, suffix = found
            return not check_already_submitted(exact, exact_for_hypothesis,
                                               found_rrids, tags, unresolved_exacts)

        def resolver(found):
            prefix, exact, exact_for_hypothesis, suffix = found
            return rrid_resolver_xml(exact, found_rrids)

        def submitter(found, resolved):
            return submit_to_h(target_uri, document, found, resolved, h, found_rrids,
                               existing, existing_with_suffixes)

        processText = make_find_check_resolve_submit(finder, checker, resolver, submitter)

        responses = list(processText(cleaned_text))  # this call runs everything

        results = ', '.join(found_rrids.keys())
        write_stdout(target_uri, document, doi, pmid, found_rrids, head, body, text, h)
        write_log(target_uri, document, doi, pmid, found_rrids, head, body, text, h)

    except BaseException as e:
        # there are some other linger issues that are what was causing
        # uris to get stuck as always running in sync
        log.exception(e)
        raise e

    finally:
        URL_LOCK.stop_uri(target_uri)

    return results, 200, {'Content-Type': 'text/plain',
                          'Access-Control-Allow-Origin':'*'}


def rrid_OPTIONS(request):
    try:
        request_headers = request.headers['Access-Control-Request-Headers'].lower()
        request_headers = re.findall('\w(?:[-\w]*\w)', request_headers)
    except KeyError:
        request_headers = []
    response_headers = ['access-control-allow-origin']
    for req_acoa_header in request_headers:
        if req_acoa_header not in response_headers:
            response_headers.append(req_acoa_header)
    response_headers = ','.join(response_headers)
    return '', 204, {'Access-Control-Allow-Origin': '*',
                     'Access-Control-Allow-Headers': response_headers}


def rrid_wrapper(request, h, logloc, URL_LOCK):
    """ Receive an article, parse RRIDs, resolve them, create annotations, log results """
    if  request.method == 'OPTIONS':
        return rrid_OPTIONS(request)
    elif request.method == 'POST':
        return rrid_POST(request, h, logloc, URL_LOCK)
    else:
        return abort(405)


def main(local=False):
    from scibot.config import api_token, username, group, group2
    print(username, group, group2)  # sanity check
    from scibot.sync import __doc__ as sync__doc__, Locker, client
    from scibot.config import syncword
    if syncword is None:
        raise KeyError('Please set the SCIBOT_SYNC environment variable')

    from docopt import docopt, parse_defaults
    _sdefaults = {o.name:o.value if o.argcount else None for o in parse_defaults(sync__doc__)}
    _backup_sync_port = int(_sdefaults['--port'])

    loop = asyncio.get_event_loop()
    app = Flask('scibot bookmarklet server')
    app.config['loop'] = loop

    h = HypothesisUtils(username=username, token=api_token, group=group)
    h2 = HypothesisUtils(username=username, token=api_token, group=group2)

    if __name__ == '__main__':
        args = docopt(__doc__)
        _sync_port = args['--sync-port']

        if _sync_port:
            sync_port = int(_sync_port)
        else:
            sync_port = _backup_sync_port
    else:
        sync_port = _backup_sync_port

    chan = 'localhost', sync_port

    # TODO
    #try:
    #except AuthenticationError as e:
        #raise e
    send = run(client, chan, syncword)
    URL_LOCK = Locker(send)
    app.URL_LOCK = URL_LOCK

    #@app.route('/synctest', methods=['GET'])
    def synctest():
        URL_LOCK.start_uri('a-test-uri')
        URL_LOCK.stop_uri('a-test-uri')
        return 'test-passed?'

    synctest()

    @app.route('/controlled-tags', methods=['GET'])
    def route_controlled_tags():
        curator_tags = curatorTags()  # TODO need client support for workflow:RRID -> * here
        return '\n'.join(curator_tags), 200, {'Content-Type':'text/plain; charset=utf-8'}

    @app.route('/rrid', methods=['POST', 'OPTIONS'])
    def rrid():
        return rrid_wrapper(request, h, 'logs/rrid/', URL_LOCK)

    @app.route('/validaterrid', methods=['POST', 'OPTIONS'])
    def validaterrid(request):
        return rrid_wrapper(request, h2, 'logs/validaterrid/', URL_LOCK)

    @app.route('/bookmarklet', methods=['GET'])
    def bookmarklet():
        return bookmarklet_wrapper(request, 'rrid')

    @app.route('/validatebookmarklet', methods=['GET'])
    def validatebookmarklet():
        return bookmarklet_wrapper(request, 'validaterrid')

    @app.route('/export', methods=['GET'])
    def export():
        print('starting csv export')
        output_rows, DATE = export_impl()
        data = StringIO()
        writer = csv.writer(data)
        writer.writerows(sorted(output_rows))
        return gzip.compress(data.getvalue().encode()), 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment;filename = RRID-data-%s.csv' % DATE,
            'Content-Encoding': 'gzip'}

    @app.route('/export.json', methods=['GET'])
    def export_json():
        print('starting json export')
        output_json, DATE = export_json_impl()
        data = json.dumps(output_json, sort_keys=True, indent=4)

        return gzip.compress(data.encode()), 200, {
            'Content-Type': 'application/json',
            'Content-Encoding': 'gzip'}

    if not local:
        return app
    else:
        from os.path import expanduser
        from wsgiref.simple_server import make_server
        from scibot.config import test_host, port_bookmarklet

        print('no login detected, running on localhost only')
        host = test_host
        port = port_bookmarklet

        print('host: %s, port %s' % ( host, port ))
        server = make_server(host, port, app)
        # openssl req -new -x509 -keyout scibot-self-sign-temp.pem -out scibot-self-sign-temp.pem -days 365 -nodes
        #server.socket = ssl.wrap_socket(server.socket,
                                        #keyfile='/etc/letsencrypt/live/scibot.scicrunch.io/privkey.pem',
                                        #certfile='/etc/letsencrypt/live/scibot.scicrunch.io/fullchain.pem',
                                        #server_side=True)
        server.socket = ssl.wrap_socket(server.socket,
                                        keyfile=expanduser('~/files/certs/scibot_test/tmp-nginx.key'),
                                        certfile=expanduser('~/files/certs/scibot_test/tmp-nginx.crt'),
                                        server_side=True)
        server.serve_forever()


if __name__ == '__main__':
    main(local=True)
