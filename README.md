# RRID (aka NIFbot)

A tool and companion service used to:

* find RRIDs in articles 
* look them up in the SciCrunch resolver
* create Hypothesis annotations that anchor to the RRIDs and display lookup results

## Getting Started

* Create the Hypothesis account under which annotations will be created
* Specify HOST, PORT, USERNAME, and PASSWORD 
* python rrid.py
* note and install missing libraries
* python rrid.py

## Capturing the bookmarklet

Visit http://HOST:8080/bookmarklet which produces this page:

  To install the bookmarklet, drag this link -- rrid -- to your bookmarks bar.

  If you need to copy/paste the bookmarklet's code into a bookmarklet, it's here:

  javascript:(function(){var xhr=new XMLHttpRequest();var params='uri='+location.href+'&data='+encodeURIComponent(document.body.innerText);xhr.open('POST','http://localhost:8081/rrid',true);xhr.setRequestHeader('Content-type','application/x-www-form-urlencoded');xhr.setRequestHeader('Access-Control-Allow-Origin','*');xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: '+xhr.responseText)};xhr.send(params)}());

## Using the bookmarklet

Visit an article that contains RRIDs, click the bookmarklet

## Checking results in the browser

The found RRIDs are logged to the JavaScript console

## Checking results on the server

The found RRIDs are logged to timestamped files, along with the text of the article that was scanned for RRIDs

