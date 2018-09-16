form_data = {'body': ['\n'
                      '<h1>SciBot</h1>\n'
                      '<p>To install the bookmarklet, drag this link -- <a '
                      'href="javascript:(function(){var xhr=new XMLHttpRequest();var '
                      "params='uri='+location.href+'&amp;head='+encodeURIComponent(document.head.innerHTML)+'&amp;body='+encodeURIComponent(document.body.innerHTML)+'&amp;data='+encodeURIComponent(document.body.innerText);xhr.open('POST','https://localhost:4443/rrid',true);xhr.setRequestHeader('Content-type','application/x-www-form-urlencoded');xhr.setRequestHeader('Access-Control-Allow-Origin','*');xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: "
                      '\'+xhr.responseText)};xhr.send(params)}());">SciBot '
                      'localhost:4443</a> -- to your bookmarks bar.</p>\n'
                      "<p>If you need to copy/paste the bookmarklet's code into a "
                      "bookmarklet, it's here:</p>\n"
                      '<code>\n'
                      'javascript:(function(){var xhr=new XMLHttpRequest();\n'
                      '\n'
                      "var params='uri='+location.href+\n"
                      "'&amp;head='+encodeURIComponent(document.head.innerHTML)+\n"
                      "'&amp;body='+encodeURIComponent(document.body.innerHTML)+\n"
                      "'&amp;data='+encodeURIComponent(document.body.innerText);\n"
                      '\n'
                      "xhr.open('POST','https://localhost:4443/rrid',true);\n"
                      "xhr.setRequestHeader('Content-type','application/x-www-form-urlencoded');\n"
                      "xhr.setRequestHeader('Access-Control-Allow-Origin','*');\n"
                      "xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: "
                      "'+xhr.responseText)};\n"
                      'xhr.send(params)}());\n'
                      '</code>\n'
                      '\n'
                      '\n'],
             'data': ['SciBot\n'
                      '\n'
                      'To install the bookmarklet, drag this link -- SciBot localhost:4443 '
                      '-- to your bookmarks bar.\n'
                      '\n'
                      "If you need to copy/paste the bookmarklet's code into a "
                      "bookmarklet, it's here:\n"
                      '\n'
                      'javascript:(function(){var xhr=new XMLHttpRequest(); var '
                      "params='uri='+location.href+ "
                      "'&head='+encodeURIComponent(document.head.innerHTML)+ "
                      "'&body='+encodeURIComponent(document.body.innerHTML)+ "
                      "'&data='+encodeURIComponent(document.body.innerText); "
                      "xhr.open('POST','https://localhost:4443/rrid',true); "
                      "xhr.setRequestHeader('Content-type','application/x-www-form-urlencoded'); "
                      "xhr.setRequestHeader('Access-Control-Allow-Origin','*'); "
                      "xhr.onreadystatechange=function(){if(xhr.readyState==4)console.log('rrids: "
                      "'+xhr.responseText)}; xhr.send(params)}());"],
             'head': ['\n'
                      '<style>\n'
                      'h1 { font-family: Arial,sans-serif; color: #777; font-size: 36px; '
                      'font-weight: normal }\n'
                      'body { font-family: verdana; margin:.75in }\n'
                      '</style>\n'
                      '<title>SciBot bookmarklet</title>'],
'uri': ['https://localhost:4443/bookmarklet']}
