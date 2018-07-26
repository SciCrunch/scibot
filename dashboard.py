#!/usr/bin/env python3.6
import os
import pickle
import subprocess
import html
from pathlib import PurePath
from os import environ
from forms import SearchForm
from scibot.release import Curation
from scibot.rrid import PMID, DOI
from scibot.export import bad_tags
from pyontutils.utils import anyMembers
from pyontutils.htmlfun import render_table, htmldoc, atag, divtag
from pyontutils.htmlfun import table_style, navbar_style
 
from hyputils.subscribe import preFilter, AnnotationStream
from hyputils.handlers import helperSyncHandler, filterHandler
from hyputils.hypothesis import Memoizer
from flask import Flask
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from IPython import embed
from wtforms import Form, StringField, SelectField
bp = Blueprint('Search', __name__)

print('END IMPORTS')

api_token = environ.get('RRIDBOT_API_TOKEN', 'TOKEN')  # Hypothesis API token
username = environ.get('RRIDBOT_USERNAME', 'USERNAME') # Hypothesis username
group = environ.get('RRIDBOT_GROUP', '__world__')
group_staging = environ.get('RRIDBOT_GROUP_STAGING', '__world__')
print(api_token, username, group)  # sanity check

READ_ONLY = True
if group_staging == '__world__' and not READ_ONLY:
    raise IOError('WARNING YOU ARE DOING THIS FOR REAL PLEASE COMMENT OUT THIS LINE')

#memfile = '/tmp/real-scibot-annotations.pickle'
if group.startswith('5'):
    print('Real annos')
    memfile = '/tmp/real-scibot-annotations.pickle'
elif group.startswith('4'):
    print('Test annos')
    memfile = '/tmp/test-scibot-annotations.pickle'

def route(route_name):
    def wrapper(function):
        def inner(*args, **kwargs):
            print(route_name)
            return function(*args, **kwargs)
        return inner
    return wrapper

def make_app(annos):
    app = Flask('scibot dashboard')
    [Curation(a, annos) for a in annos]
    #[Curation(a, annos) for a in annos]
    base_url = '/dashboard/'
    names = ['missing', 'incorrect', 'papers', 'unresolved', 'no-pmid', 'no-annos', 'table', 'Journals']
    for name in names:
        with open(f'{name}.txt','wt') as f:
            f.write('')

    def tag_string(c):
        return ' '.join(sorted(t.replace('RRIDCUR:', '') for t in c.tags if 'RRIDCUR' in t))

    def filter_rows(*tags):
        if not tags:
            ff = lambda t: True
        else:
            ff = lambda ltags: anyMembers(ltags, *tags)
        yield from ((str(i + 1),
                     tag_string(c),
                     atag(PMID(c.pmid), c.pmid, new_tab=True)
                     if c.pmid
                     else (atag(DOI(c.doi), c.doi, new_tab=True) if c.doi else ''),
                     atag(c.shareLink, 'Annotation', new_tab=True) if c else atag(c.uri, 'Paper', new_tab=True),
                     c.user,
                     c.text if c.user != 'scibot' and c.text else '')
                    for i, c in enumerate(sorted((c for c in Curation
                                                  if ff(c.tags)),
                                                 key=tag_string
                                                )))
    k = 0
    kList = []
    URLDict = {}
    for h in Curation:
        if BaseURL(h._anno) in URLDict.keys():
            URLDict[BaseURL(h._anno)] += 1
        else:
            URLDict[BaseURL(h._anno)] = 1
            kList.append(k)

    class NavBar:
        def __call__(self):
            return divtag(atag(url_for('route_base'), 'Home'),
                          atag(url_for('route_papers'), 'Papers'),
                          atag(url_for('route_anno_incorrect'), 'Incorrect'),
                          atag(url_for('route_anno_unresolved'), 'Unresolved'),
                          atag(url_for('route_anno_missing'), 'Missing'),
                          atag(url_for('route_no_pmid'), 'No PMID'),
                          atag(url_for('route_no_annos'), 'No annos'),
                          atag(url_for('route_table'), 'All'),
                          atag(url_for('route_anno_search'), 'Search'),
                          # TODO search box
                          cls='navbar')

    navbar = NavBar()

    def table_rows(rows, title):
        return htmldoc(navbar(),
                       divtag(render_table(rows, '#', 'Problem', 'Identifier', 'Link', 'Curator', 'Notes'),
                              cls='main'),
                       title=title,
                       styles=(table_style, navbar_style))

    def nonestr(thing):
        return '' if thing is None else thing

    def no_pmid():
        return sorted(((atag(url, '...' + url[-20:]),
                        nonestr(rrids.pmid),
                        '' if rrids.doi is None else atag(DOI(rrids.doi), rrids.doi),
                        str(len(rrids)),
                        str(len([a for r in rrids.values() for a in r])))
                       for url, rrids in Curation._papers.items()
                       if rrids.pmid is None),
                      key=lambda r: int(r[3]),
                      reverse=True)

    def no_annos():  # TODO
        return []

    @app.route('/css/table.css')
    def route_css_table_style():
        return table_style, 200, {'Content-Type':'text/css'}

    @app.route('/dashboard', methods=('GET', 'POST'))
    def route_base():
        return render_template('main.html', method='get',
                               navbar=navbar(),
                               navbar_style = navbar_style,
                               var='We have a lot of work to do!',
                               nmissing='??',
                               nures='??',
                               incor='??',
                               npapers=str(len(Curation._papers)),
                               nnopmid=str(len(no_pmid())),
                               #nnoannos=str(len(no_annos()))
                               nnoannos='??',
                               allp='??',)

    @app.route('/dashboard/anno-count')
    def route_anno_count():
        return str(len(Curation._annos_list))

    #@app.route(PurePath(base_url, 'anno-tags').as_posix())
    @app.route('/dashboard/anno-user/<user>')
    def route_anno_tags(user):
        print(user)
        out = '\n'.join([f'{anno.user} {anno.text} {anno.tags}<br>' for anno in Curation._annos_list if anno.user == user])
        #embed()
        return out

    @app.route('/dashboard/refresh')
    def route_refresh():
        return redirect('/dashboard')

    @app.route('/dashboard/journals')
    def route_Journals():
        file = open("Journals.txt","r")
        paperStr = file.read()
        file.close()
        if paperStr == '':
            h = 0
            URLList = []
            counter = 0
            paperStr = str(counter) + ' Results:<br><br>'
            print("PROSSESING")
            for h in Curation:
                journal = Journal(h._anno)
                if "urn:x-pdf" in journal or "file:" in journal:
                    URLList.append(journal)
                if journal == "":
                    print (h.shareLink)
                if not journal in URLList:
                    paperStr += "<br> <a href=\"" + h.shareLink + "\"> Journal Link </a><br>"
                    paperStr += journal
                    counter += 1
                    URLList.append(journal)
            paperStr = str(counter) + paperStr[1:]
            file = open("Journals.txt", "w")
            file.write(paperStr)
            file.close()
        return (paperStr)	

    @app.route('/dashboard/DOI')
    def route_DOI():
        DOIStr = ""
        DOIList = []
        counter = 0
        for h in Curation:
            if [t for t in h.tags if t.startswith("DOI")]:
                if h.doi not in DOIList:
                    DOIStr += '<br> Anno #:%s <br>' % h
                    DOIStr += '<a href=' + h.shareLink + '> Anno Link </a><br>'
                    DOIStr += h.doi
                    counter += 1
                    if h.doi:
                        DOIList.append(h.doi)
        return (str(counter) + "<br><br>" + DOIStr)

    @app.route('/dashboard/NoFurtherAction')
    def route_NFA():
        file = open("NFA.txt")
        returnStr = file.read()
        file.close()
        if returnStr == '':
            h = 0
            a = 0 
            counter = 0
            returnStr += """0 Problems:
                            <html>
                            <style type="text/css">
                              td {width: 300px; hight 40px}     
                              td {border: 1px solid #000000;}
                              a.class1:link {
                                background-color: #009cdb;
                                color: white;
                                padding: 14px 25px;
                                text-align: center;
                                text-decoration: none;
                                display: inline-block;
                            }
                              a.class2:visited, a.class2:link{
                                background-color: #fcff56;
                                color: black;
                                padding: 14px 25px;
                                text-align: center;
                                text-decoration: none;
                                display: inline-block;
                            }
                              a.class1:visited {
                                background-color: #db4500;
                                color: white;
                            }

                              a.class1:hover, a.class1:active, a.class2:hover, a.class2:active {background-color: red;}
                            </style>
                            <table cellpadding = 3 cellspacing = 0>
                            <tr>
                              <td width: 70px>#</td>
                              <td>Problem</th>
                              <td>PMID</th>
                              <td>Link</th>
                              <td>Annotated By</th>
                              <td>Notes</th>
                            </tr>
                            """
            URLList = []
            URLsUsed = []
            DOIDict = {}
            URLwDOI = {}
            PMIDDict = {}
            URLList.append('curation.scicrunch.com/paper/2')
            URLList.append('curation.scicrunch.com/paper/1')
            URLList.append('scicrunch.org/resources')
            print("PROSSESING")
            for h in Curation:
                if [t for t in h.tags if t.startswith("DOI")]:
                    URL = BaseURL(h._anno)
                    if not URL in URLsUsed:
                        if h.doi not in DOIDict.keys():
                            DOIDict[h.doi] = []
                        DOIDict[h.doi].append(URL)
                        URLwDOI[URL] = h.doi
                        URLsUsed.append(URL)
            for h in Curation:
                k = 0
                URL = BaseURL(h._anno)
                if [t for t in h.tags if t.startswith("PMID")]:
                    PMID = [t.replace("PMID:", "") for t in h.tags if t.startswith("PMID")][0]
                    if URL in URLsUsed:
                        for k in range(0, len(DOIDict[URLwDOI[URL]])):
                                PMIDDict[DOIDict[URLwDOI[URL]][k]] = PMID
                    else:
                        PMIDDict[URL] = PMID
            #print(str(len(Curation._annos_list)))
            for h in Curation:
                URL = BaseURL(h._anno)
                if URL in PMIDDict.keys():
                    PMID = PMIDDict[URL]
                    PMID = f'<a href="https://www.ncbi.nlm.nih.gov/pubmed/{PMID}" class="class2" target="_blank">PMID:{PMID}</a>'
                elif not URL in URLList:
                    counter += 1
                    if URL in URLwDOI.keys():
                        PMID = '<a href=https://www.ncbi.nlm.nih.gov/pubmed/?term='+URLwDOI[URL].replace("['","").replace("']","")+' class="class2" target="_blank"> PubMed </a>'
                    else:
                        PMID = '<a href="https://www.ncbi.nlm.nih.gov/pubmed/" class="class2" target="_blank"> PubMed </a>'
                    URLList.append(URL)
                if [t for t in h.tags if "NoPMID" in t]:
                    counter += 1
                    returnStr += "<tr><td>"+str(counter)+"</td><td>NO PMID</td><td>"+ PMID +"</td><td><a href=" + h._anno.uri + ' class="class1" target="_blank"> Paper Link </a></td><td>'+h._anno.user+"</td><td>"+h.text+"No Further Action"+"</td></tr>"
                if [t for t in h.tags if "InsuffiscientMetadata" in t]:
                    if not InsuffiscientMetadata in h.tags[0]:
                        problem = h.tags[0].replace("RRIDCUR: ", "")
                    else:
                        problem = h.tags[1].replace("RRIDCUR: ", "")
                    counter += 1
                    returnStr += "<tr><td>"+str(counter)+"</td><td>"+problem+"</td><td>"+ PMID +"</td><td><a href=" + h.shareLink + ' class="class1" target="_blank"> Anno Link </a></td><td>'+h._anno.user+"</td><td>"+h.text+"No Further Action"+"</td></tr>"
            returnStr += "</table></html>"
            returnStr =  '<a href=/dashboard class="class2"> BACK </a><br>' + str(counter) + returnStr[1:]
            file = open("NFA.txt", "w")
            file.write(returnStr)
            file.close()
        return(returnStr)

    @app.route('/dashboard/table')
    def route_table():
        rows = filter_rows(Curation.INCOR_TAG, 'RRIDCUR:Unresolved', 'RRIDCUR:Missing', *bad_tags)
        return table_rows(rows, 'All SciBot curation problems')

        """
        <style type="text/css">
            td {width: 300px; hight 40px}     
            td {border: 1px solid #000000;}
            a.class1:link {
                background-color: #aaaaff;
                color: white;
                padding: 14px 25px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
            }
              a.class2:visited, a.class2:link{
                  background-color: #79c478;

                  color: black;
                  padding: 14px 25px;
                  text-align: center;
                  text-decoration: none;
                  display: inline-block;
              }
              a.class1:visited {
                  background-color: #009cdb;
                  color: white;
              }

              a.class1:hover, a.class1:active, a.class2:hover, a.class2:active {background-color: red;}
        </style>"""

    @app.route('/dashboard/no-annos')
    def route_no_annos():
        return htmldoc(navbar(),
                       divtag('There shouldn\'t be anything here...',
                              cls='main'),
                       styles=(navbar_style,))

    @app.route('/dashboard/papers')
    def route_papers():
        rows = sorted(((atag(url, '...' + url[-20:]),
                        nonestr(rrids.pmid),
                        nonestr(rrids.doi),
                        str(len(rrids)),
                        str(len([a for r in rrids.values() for a in r])))
                       for url, rrids in Curation._papers.items()),
                      key=lambda r: int(r[3]),
                      reverse=True)
        return htmldoc(navbar(),
                       divtag(render_table(rows, 'Paper', 'PMID', 'DOI', 'RRIDs', 'Annotations'),
                              cls='main'),
                       title='SciBot papers',
                       styles=(table_style, navbar_style))

    @app.route('/dashboard/no-pmid')
    def route_no_pmid():
        rows = no_pmid()
        return htmldoc(navbar(),
                       divtag(render_table(rows, 'Paper', 'PMID', 'DOI', 'RRIDs', 'Annotations'),
                              cls='main'),
                       title='SciBot papers',
                       styles=(table_style, navbar_style))



    @app.route('/dashboard/incorrect')
    def route_anno_incorrect():
        rows = filter_rows(Curation.INCOR_TAG)
        return table_rows(rows, 'Incorrect RRIDs')

    @app.route('/dashboard/unresolved')
    def route_anno_unresolved():
        rows = filter_rows('RRIDCUR:Unresolved')
        return table_rows(rows, 'Unresolved RRIDs')

    @app.route('/dashboard/results')
    def search_results(search):
        h = 0
        hlist = []
        hstr = ''
        counter = 0
    #    if search.data['search'] == '':
    #        h = 0
    #        hstr = ''
    #        for h in Curation:
    #            hstr += repr(h)
    #            h += 1
    #        return(hstr)
    #    else:
        if search.data['select'] == 'ID':
            for h in Curation:
                if search.data['search'] in h.id:
                    hstr += '<br> Anno #:%s <br>' % h
                    hstr += '<a href=' + h.shareLink + '> Anno Link </a><br>'
                    hstr += repr(h)
                    counter += 1
            if hstr == '':
                return('no results')
            return (str(counter) + ' Results:<br><br>' + hstr)
            #return render_template('results.html', results=html.unescape(hstr))
        elif search.data['select'] == 'Tags':
            for h in Curation:
                if [t for t in h.tags if search.data['search'] in t]:
                    hstr += '<br> Anno #:%s <br>' % h
                    hstr += '<a href=' + h.shareLink + '> Anno Link </a><br>'
                    hstr += repr(h)
                    counter += 1
            if hstr == '':
                return('no results')
            print (str(len(hlist)))
            print(len(Curation._annos_list))
            return (str(counter) + ' Results:<br><br>' + hstr)
            #return render_template('results.html', results=hstr)
        elif search.data['select'] == 'User':
            for h in Curation:
                if h._anno.user == search.data['search']:
                    hstr += '<br> Anno #:%s <br>' % h
                    hstr += '<a href=' + h.shareLink + '> Anno Link </a><br>'
                    hstr += repr(h)
                    counter += 1
            if hstr == '':
                return('no results')
            return (str(counter) + ' Results:<br><br>' + hstr)
        else:
            return search_text(search.data['select'], Curation._annos_list, list(Curation), search.data['search'])

    @app.route('/dashboard/anno-search', methods=('GET', 'POST'))
    def route_anno_search():
        search = SearchForm(request.form)
        if request.method == 'POST':
            return search_results(search)
        return render_template('search.html',
                               form=search,
                               navbar=navbar(),
                               navbar_style=navbar_style,
                              )

    @app.route('/dashboard/missing', methods=('GET', 'POST'))
    def route_anno_missing():
        rows = filter_rows('RRIDCUR:Missing')
        return table_rows(rows, 'Missing RRIDs')

    #new_function = route('/my/route')(route_base)

    #return new_function
    return app
    #new_function_outside = make_app('not really annos')
def search_text(text, annos,  search):
        h = 0
        hlist = []
        hstr = ''
        counter = 0
        for h in Curation:
            hsplit = h.text.split('<p>',h.text.count('<p>'))
            t = 0
            Data = ''
            for t in range(0, len(hsplit)):
                if text in hsplit[t]:
                    Data = hsplit[t].replace(text + ': ', '')
            
            if search.upper() in Data.upper():
                hstr += '<br> Anno #:%s <br>' % h
                hstr += '<a href=' + h.shareLink + '> Anno Link </a><br>'
                hstr += repr(h)
                hstr += "<br>" + BaseURL(annos[h])
                counter += 1
        if hstr == '':
            return('no results')
        return (str(counter) + ' Results:<br><br>' + hstr)

def BaseURL(anno):
    URL = anno.uri.replace(".long", "").replace("/abstract", "").replace("/full","").replace(".short", "").replace(".full", "").replace("http://","").replace("https://","").replace("/FullText","").replace("/Abstract","").replace("/enhanced","")
    SplitURL = URL.split("/", URL.count("/"))
    if SplitURL[-1] == '':
        URL = SplitURL[0] + SplitURL[-2]
    else:
        URL = SplitURL[0] + SplitURL[-1]
    return URL

def Journal(anno):
    URL = anno.uri.replace(".long", "").replace("/abstract", "").replace("/full","").replace(".short", "").replace(".full", "").replace("http://","").replace("https://","").replace("/FullText","").replace("/Abstract","").replace("/enhanced","")
    SplitURL = URL.split("/", URL.count("/"))
    if len(SplitURL) == 1 or len(SplitURL) == 0:
        print(URL)
    URL = SplitURL[0]
    return URL

def annoSync(memfile, helpers=tuple()):
    if group == '__world__':
        raise ValueError('Group is set to __world__ please run the usual `export HYP_ ...` command.')
    get_annos = Memoizer(memfile, api_token, username, group, 200000)
    yield get_annos
    prefilter = preFilter(groups=[group]).export()
    helperSyncHandler.memoizer = get_annos
    helperSyncHandler.helpers = helpers
    annos = get_annos()
    yield annos
    stream_loop = AnnotationStream(annos, prefilter, helperSyncHandler)()
    yield stream_loop

def setup():
    get_annos, annos, stream_loop = annoSync(memfile, (Curation,))
    stream_loop.start()
    app = make_app(annos)
    app.debug=False
    return app

def main():
    get_annos, annos, stream_loop = annoSync(memfile, (Curation,))
    app = make_app(annos)
    #stream_loop.start()
    app.secret_key = 'super secret key'
    app.config['SESSION_TYPE'] = 'filesystem'
    print(app.view_functions)
    app.debug = True
    app.run(host='localhost', port=8080)
    #embed()

if __name__ == '__main__':
    main()
