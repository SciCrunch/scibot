#!/usr/bin/env python3
from __future__ import print_function
from os import environ
from collections import defaultdict
from hypothesis import HypothesisUtils, HypothesisAnnotation
from IPython import embed
from collections import namedtuple, defaultdict

username = environ.get('RRIDBOT_USERNAME', 'USERNAME')  # Hypothesis account
password = environ.get('RRIDBOT_PASSWORD', 'PASSWORD')
group = environ.get('RRIDBOT_GROUP', '__world__')
print(username, group)  # sanity check
    
h = HypothesisUtils(username=username, password=password, group=group, max_results=5000)
h.login()
params = {'group' : h.group }
rows = h.search_all(params)
annos = [HypothesisAnnotation(row) for row in rows]
annotated_urls = defaultdict(list)
for anno in annos:
    annotated_urls[anno.uri].append(anno)

html = """<html>
<head><style>
body { font-family:verdana;margin:.75in }
.anno { margin: 20px;
    border-style: solid;
    border-width: thin;
    padding: 20px; }
.text { margin:20px }
.article { font-size:larger }
</style></head>
<body>"""

rows = []
for annotated_url in annotated_urls.keys():
    print(annotated_url)
    first = annotated_urls[annotated_url][0]
    html += '<div class="article"><a href="%s">%s</a></div>' % ( first.uri, first.uri ) 
    annos = annotated_urls[annotated_url]
    if '8151' not in annotated_url:
        continue
    #row = namedtuple('rrid_row', ['PMID','RRID','TAG'])
    replies = defaultdict(list)
    for anno in annos:  # gotta build the reply structure and get pmid
        if anno.references:
            for reference in references:  # shouldn't there only be one???
                replies[reference].append(anno.id)
        PMID = [tag for tag in anno.tags if tag.startswith('PMID:')]
        if PMID:
            if len(PMID) > 1:
                print(PMID)
                raise BaseException('more than one pmid tag')
            else:
                PMID = PMID[0]

    row = []
    for annot in annos:
        
        print('id:', anno.id)
        print('user:', anno.user)
        print('text:', anno.exact)
        print('tags:', anno.tags)
        print('type:', anno.type)
        print('references:', anno.references)
        continue
        quote = 'quote: ' + anno.exact if anno.exact is not None else ''
        tags = 'tags: ' + ','.join(anno.tags) if len(anno.tags) else ''
        html += """
        <div class="anno">
        <div>user: %s</div>
        <div>%s</div>
        <div>%s</div>
        <div class="text">%s</div>
        </div>
        """ % ( anno.user, quote, tags, anno.text )

        row.append(

html += '</body></html>'

with open('rrid.html','wb') as f:
    f.write(html.encode('utf-8'))
