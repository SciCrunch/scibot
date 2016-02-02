#!/usr/bin/env python3
from __future__ import print_function
from os import environ
from collections import defaultdict
from hypothesis import HypothesisUtils, HypothesisAnnotation

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

for annotated_url in annotated_urls.keys():
    print(annotated_url)
    first = annotated_urls[annotated_url][0]
    html += '<div class="article"><a href="%s">%s</a></div>' % ( first.uri, first.uri ) 
    annos = annotated_urls[annotated_url]
    for anno in annos:
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

html += '</body></html>'

with open('rrid.html','wb') as f:
    f.write(html.encode('utf-8'))
