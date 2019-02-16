# SciBot

curation workflow automation and coordination

* find RRIDs in articles 
* look them up in the SciCrunch resolver
* create Hypothesis annotations that anchor to the RRIDs and display lookup results

## Getting Started

* [Create a Hypothesis](https://web.hypothes.is/start/) account which will post the annotations.
* Generate an api token at https://hypothes.is/profile/developer (must be logged in to see page).
* Create a group to store the annotations at https://hypothes.is/groups/new (must be logged in to see page).
* See [Setup on amazon](#setup-on-amazon)

## Capturing the bookmarklet

Visit https://HOST:PORT/bookmarklet and follow the instructions.

## Using the bookmarklet

Visit an article that contains RRIDs, click the bookmarklet

## Checking results in the browser

The found RRIDs are logged to the JavaScript console

## Checking results on the server

The found RRIDs are logged to timestamped files, along with the text and html of the article that was scanned for RRIDs

## Setup on Gentoo
As root.
```bash
layman -a tgbugs-overlay
emerge scibot
rc-config add scibot-bookmarklet default
vim /etc/conf.d/scibot-bookmarklet  # set username, group, api key, etc.
/etc/init.d/scibot-bookmarklet start
```

## Setup on ubuntu 18.04
Set `export PATH=~/.local/bin:${PATH}` in `~/.bashrc`
1. `sudo apt-get install build-essential python3-dev libxml2-dev libxslt1-dev`
2. `sudo pip3 install --user pip pipenv`
3. `git clone https://github.com/SciCrunch/scibot.git`
4. `cd scibot && pipenv install`
5. `pipenv shell` to get an environment with acess to all the required libraries.
6. Inside the pipenv shell (after following steps 6-10 below) you should
be able to run commands like `python scibot/export.py`.

## Setup on amazon

0. ssh in to the host that will serve the script
1. `sudo yum install gcc libxml2 libxml2-devel libxslt libxslt-devel python36 python36-devel python36-pip`
2. `sudo alternatives --set python /usr/bin/python3.6`
3. `sudo pip install pipenv`
4. `git clone https://github.com/SciCrunch/scibot.git`
5. `cd scibot && python3.6 setup.py wheel && pipenv install dist/*.whl`
6. `export SCIBOT_USERNAME=someusername`
7. `export SCIBOT_GROUP=somegroupname`
8. `unset HISTFILE`
9. `export SCIBOT_API_TOKEN=sometoken`
10. `export SCIBOT_SYNC=somerandomnumber` (e.g. run `head -c 100 /dev/urandom | tr -dc 'a-zA-Z0-9'` every time)
11. create a screen session
12. in the screen session run `pipenv run scibot-server` you should create a link to the log files folder in ~/scibot/
13. get letsencrypt certs using certbot, follow directions [here](https://certbot.eff.org/docs/using.html) (prefer standalone)
14. alternately if using a cert from another registrar you may need to bundle your certs `cat my-cert.crt existing-bundle.crt > scicrunch.io.crt` (see https://gist.github.com/bradmontgomery/6487319 for details)
15. before or after starting gunicorn you need to run `sudo yum install nginx && sudo cp ~/scibot/nginx.conf /etc/nginx/nginx.conf && sudo service start nginx`
16. run `pipenv run scibot-sync` in another screen (if run in a terminal with a different environment you need to run step 10 again first)

## Development setup
To set up scibot for development (for example if you want to run manual releases)
0. Install python3 and pip for your os (e.g. on macos use `brew`)
1. From your git folder run `git clone https://github.com/tgbugs/scibot.git`
2. `pushd scibot`
3. `pip3 install --user -e .` will install requirements and register the
scibot folder under version control with python as the scibot module.
4. `popd`
5. scibot currently makes use of my version of some of the core hypothes.is
code which is not available as a package, to install it run the following
```bash
git clone https://github.com/tgbugs/h.git
pushd h
git checkout flask-new-3
popd
echo "export PYTHONPATH=$(pwd)/h:${PYTHONPATH}" >> ~/.bashrc
# may need to be ~/.bash_profile depending on your system
source ~/.bashrc
```

## If all else fails
Make sure you have >=python3.6 and pip installed.
Clone the repo and run `python setup.py develop --user`.
