Setting up buildbot
+++++++++++++++++++

These directions provide some rough information for setting up a build bot on a Lucid machine.


Apt Installs
============

Install CKAN core dependencies from Lucid distribution (as per :doc:`README`)::

  sudo apt-get install build-essential libxml2-dev libxslt-dev 
  sudo apt-get install wget mercurial postgresql libpq-dev git-core
  sudo apt-get install python-dev python-psycopg2 python-virtualenv
  sudo apt-get install subversion

Maybe need this too::

  sudo apt-get install python-include

Buildbot software::

  sudo apt-get install buildbot

Deb building software (as per :doc:`deb`)::

  sudo apt-get install -y dh-make devscripts fakeroot cdbs 

Fabric::

  sudo apt-get install -y fabric

If you get errors with postgres and locales you might need to do these::

  sudo apt-get install language-pack-en-base
  sudo dpkg-reconfigure locales


Postgres setup
==============

If installation before failed to create a cluster, do this after fixing errors::

  sudo pg_createcluster 8.4 main --start

Create users and databases::

  sudo -u postgres createuser -S -D -R -P buildslave
  # set this password (matches buildbot scripts): biomaik15
  sudo -u postgres createdb -O buildslave ckan1
  sudo -u postgres createdb -O buildslave ckanext


Buildslave setup
================

Rough commands::

  sudo useradd -m -s /bin/bash buildslave
  sudo chown buildslave:buildslave /home/buildslave
  sudo su buildslave
  cd ~
  hg clone https://dread@bitbucket.org/okfn/buildbot-scripts .
  ssh-keygen -t rsa
  cp /home/buildslave/.ssh/id_rsa.pub  ~/.ssh/authorized_keys
  mkdir -p ckan/build
  cd ckan/build
  python ~/ckan-default.py
  buildbot create-slave ~ localhost:9989 okfn <buildbot_password>
  vim ~/info/admin
  vim ~/info/host
  mkdir /home/buildslave/pip_cache
  virtualenv pyenv-tools
  pip -E pyenv-tools install buildkit


Buildmaster setup
=================

Rough commands::

  mkdir ~/buildmaster
  buildbot create-master ~/buildmaster
  ln -s /home/buildslave/master/master.cfg ~/buildmaster/master.cfg
  cd ~/buildmaster
  buildbot checkconfig


Startup
=======

Setup the daemons for master and slave::

  sudo vim /etc/default/buildbot

This file should be edited to be like this::

  BB_NUMBER[0]=0                  # index for the other values; negative disables the bot
  BB_NAME[0]="okfn"               # short name printed on startup / stop
  BB_USER[0]="okfn"               # user to run as
  BB_BASEDIR[0]="/home/okfn/buildmaster"          # basedir argument to buildbot (absolute path)
  BB_OPTIONS[0]=""                # buildbot options
  BB_PREFIXCMD[0]=""              # prefix command, i.e. nice, linux32, dchroot

  BB_NUMBER[1]=1                  # index for the other values; negative disables the bot
  BB_NAME[1]="okfn"               # short name printed on startup / stop
  BB_USER[1]="buildslave"               # user to run as
  BB_BASEDIR[1]="/home/buildslave"          # basedir argument to buildbot (absolute path)
  BB_OPTIONS[1]=""                # buildbot options
  BB_PREFIXCMD[1]=""              # prefix command, i.e. nice, linux32, dchroot

Start master and slave (according to /etc/default/buildbot)::

  sudo /etc/init.d/buildbot start

Now check you can view buildbot at: http://localhost:8010/


Connect ports
=============

It's preferable to view the buildbot site at port 80 rather than 8010.

If there is no other web service on this machine, you might connect up the addresses using iptables::

  sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8010

Otherwise it is best to do a reverse proxy. Using apache, edit this file::

  sudo vim /etc/apache2/sites-available/buildbot.okfn.org

to be like this::

  <VirtualHost *:80>
     ServerName buildbot.okfn.org

     ProxyPassReverse ts Off
       <Proxy *>
               Order deny,allow
               Allow from all
       </Proxy>
       ProxyPass         / http://127.0.0.1:8010/
       ProxyPassReverse  / http://127.0.0.1:8010/
       ProxyPreserveHost On
  </VirtualHost>

Then::

  sudo apt-get install libapache2-mod-proxy-html
  sudo a2enmod proxy_http
  sudo a2ensite buildbot.okfn.org
  sudo /etc/init.d/apache2 reload
