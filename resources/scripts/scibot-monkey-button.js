// ==UserScript==
// @name        SciBot Button
// @namespace   https://github.com/SciCrunch/scibot/tree/master/resources/scripts
// @description Run SciBot in a way that ignores CORS
// @match       *://*/*
// @exclude     *://*.google.com/*
// @exclude     *://*.github.com/*
// @version     1.0
// @grant       GM_addStyle
// ==/UserScript==

var zNode       = document.createElement ('div');
zNode.innerHTML = '<button id="runSciBot" type="button">Run SciBot Test</button>';
zNode.setAttribute ('id', 'scibotButtonContainer');
document.body.appendChild (zNode);

//--- Activate the newly added button.
document.getElementById ("runSciBot").addEventListener (
    "click", ButtonClickAction, false
);

function ButtonClickAction (zEvent) {
    /*--- For our dummy action, we'll just add a line of text to the top
        of the screen.
    */
    document.getElementById ("scibotButtonContainer").remove();
    var xhr=new XMLHttpRequest();
    var params=('uri=' + location.href +
                '&head=' + encodeURIComponent(document.head.innerHTML) +
                '&body=' + encodeURIComponent(document.body.innerHTML) +
                '&data=' + encodeURIComponent(document.body.innerText));
    xhr.open('POST', 'https://scibot.scicrunch.io/rrid', true);
    xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
    xhr.setRequestHeader('Access-Control-Allow-Origin', '*');
    xhr.onreadystatechange=function(){if(xhr.readyState==4) console.log('rrids: ' + xhr.responseText)};
    xhr.send(params)
}

GM_addStyle ( `
    #scibotButtonContainer {
        position:               absolute;
        top:                    0;
        left:                   0;
        font-size:              20px;
        background:             orange;
        border:                 3px outset black;
        margin:                 5px;
        opacity:                0.9;
        z-index:                9999;
        padding:                5px 20px;
    }
    #runSciBot {
        cursor:                 pointer;
    }
    #scibotButtonContainer p {
        color:                  red;
        background:             white;
    }
` );
