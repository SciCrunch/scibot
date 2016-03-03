# RRID (aka SciBot)

A tool and companion service used to:

* find RRIDs in articles 
* look them up in the SciCrunch resolver
* create Hypothesis annotations that anchor to the RRIDs and display lookup results

## Getting Started

* Create the Hypothesis account under which annotations will be created
* Specify HOST, PORT, API TOKEN, and USERNAME
* python rrid.py
* note and install missing libraries
* python rrid.py

## Capturing the bookmarklet

Visit http://HOST:PORT/bookmarklet which produces this page:

  To install the bookmarklet, drag this link -- rrid -- to your bookmarks bar.

  If you need to copy/paste the bookmarklet's code into a bookmarklet, it's here:

  javascript:(function(){var xhr=new XMLHttpRequest();var params='uri='+location.href+'&data='+encodeURIComponent(document.body.innerText);xhr.open('POST','http://localhost:8080/rrid',true);xhr.setRequestHeader('Content-type','application/x-www-form-urlencoded');xhr.setRequestHeader('Access-Control-Allow-Origin','*');xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: '+xhr.responseText)};xhr.send(params)}());

## Using the bookmarklet

Visit an article that contains RRIDs, click the bookmarklet

## Checking results in the browser

The found RRIDs are logged to the JavaScript console

## Checking results on the server

The found RRIDs are logged to timestamped files, along with the text of the article that was scanned for RRIDs

## Setup on amazon

0. ssh in to the host that will serve the script
1. `sudo yum install gcc libxml2 libxml2-devel libxslt libxslt-devel python34 python34-devel python34-pip`
2. `sudo alternatives --set python /usr/bin/python3.4`
3. `sudo pip install requests pyramid lxml`
4. clone this repository
5. change host and port for external http access
6. `unset HISTFILE`
7. `export RRIDBOT_API_TOKEN=sometoken`
8. `export RRIDBOT_USERNAME=someusername`
9. create a screen session
10. in the screen session run `sudo -E ~/rrid/rrid.py` in the folder where you want to save the log files (-E preserves the environment variables)
