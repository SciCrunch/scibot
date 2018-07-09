#!/usr/bin/env python3.6

import os
import pickle
import subprocess
import html
print ("importing....")
from pathlib import PurePath
from os import environ
from forms import SearchForm
from hyputils.hypothesis import HypothesisUtils, HypothesisAnnotation, HypothesisHelper, Memoizer, idFromShareLink, shareLinkFromId
from flask import Flask
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from IPython import embed
from wtforms import Form, StringField, SelectField
 
bp = Blueprint('Search', __name__)

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

get_annos = Memoizer(memfile, api_token, username, group, 200000)

class Dashboard1(HypothesisHelper):
    def __repr__(self, depth=0):
        out = super().__repr__(depth=depth)
        return 'MODIFIED<br>\n' + out

def route(route_name):
    def wrapper(function):
        def inner(*args, **kwargs):
            print(route_name)
            return function(*args, **kwargs)
        return inner
    return wrapper

def make_app(annos):
    app = Flask('scibot dashboard')
    hh = [Dashboard1(a, annos) for a in annos]

    base_url = '/dashboard/'

    @app.route('/dashboard')
    def route_base():
        return 'hello world'

    @app.route('/dashboard/anno-count')
    def route_anno_count():
        return str(len(annos))

    #@app.route(PurePath(base_url, 'anno-tags').as_posix())
    @app.route('/dashboard/anno-user/<user>')
    def route_anno_tags(user):
        print(user)
        out = '\n'.join([f'{anno.user} {anno.text} {anno.tags}<br>' for anno in annos if anno.user == user])
        #embed()
        return out

    @app.route('/dashboard/anno-zero-pretty')
    def route_anno_zero_pretty():
        return repr(hh[0])

    @app.route('/dashboard/results')
    def search_results(search):
        h = 0
        hlist = []
        hstr = ''
        counter = 0
    #    if search.data['search'] == '':
    #        h = 0
    #        hstr = ''
    #        for h in range(0, len(annos)):
    #            hstr += repr(hh[h])
    #            h += 1
    #        return(hstr)
    #    else:
        if search.data['select'] == 'ID':
            for h in range(0, len(annos)):
                if hh[h].id.startswith(search.data['search']):
                    hstr += '<br> Anno #:%s <br>' % h
                    hstr += repr(hh[h])
                    hlist.extend([h])
                    counter += 1
            for h in range(0, len(annos)):
                if hh[h].id.find(search.data['search']) != -1 and not h in hlist:
                    hstr += '<br> Anno #:%s <br>' % h
                    hstr += repr(hh[h])
                    counter += 1
            if hstr == '':
                return('no results')
            #return (str(counter) + ' Results:<br><br>' + hstr)
            return render_template('results.html', results=html.unescape(hstr))
        elif search.data['select'] == 'Tags':
            for h in range(0, len(annos)):
                if search.data['search'] in hh[h].tags:
                    hstr += '<br> Anno #:%s <br>' % h
                    hstr += repr(hh[h])
                    hlist.extend([h])
                    counter += 1
            for h in range(0, len(annos)):
                if [t for t in hh[h].tags if t.startswith(search.data['search'])] and not h in hlist:
                    hstr += '<br> Anno #:%s <br>' % h
                    hstr += repr(hh[h])
                    hlist.extend([h])
                    counter += 1
            for h in range(0, len(annos)):
                if [t for t in hh[h].tags if search.data['search'] in t] and not h in hlist:
                    hstr += '<br> Anno #:%s <br>' % h
                    hstr += repr(hh[h])
                    hlist.extend([h])
                    counter += 1
            if hstr == '':
                return('no results')
            print (str(len(hlist)))
            print (len(annos))
            return (str(counter) + ' Results:<br><br>' + hstr)
            #return render_template('results.html', results=hstr)
        else:
            return search_text(search.data['select'], annos, hh, search.data['search'])

    @app.route('/dashboard/anno-search', methods=('GET', 'POST'))
    def route_anno_search():
        search = SearchForm(request.form)
        if request.method == 'POST':
            return search_results(search)
        return render_template('search.html', form=search)

    #new_function = route('/my/route')(route_base)

    #return new_function
    return app
    #new_function_outside = make_app('not really annos')
def search_text(text, annos, hh, search):
        h = 0
        hlist = []
        hstr = ''
        counter = 0
        for h in range(0, len(annos)):
            hsplit = hh[h].text.split('<p>',hh[h].text.count('<p>'))
            t = 0
            Data = ''
            for t in range(0, len(hsplit)):
                if text in hsplit[t]:
                    Data = hsplit[t].replace(text + ': ', '')
            
            if search.upper() in Data.upper():
                hstr += '<br> Anno #:%s <br>' % h
                hstr += repr(hh[h])
                hlist.extend([h])
                counter += 1
        if hstr == '':
            return('no results')
        return (str(counter) + ' Results:<br><br>' + hstr)

def main():
    annos = get_annos()
    app = make_app(annos)
    app.secret_key = 'super secret key'
    app.config['SESSION_TYPE'] = 'filesystem'
    print(app.view_functions)
    app.debug = True
    app.run(host='localhost', port=8080)
    #embed()

if __name__ == '__main__':
    main()
