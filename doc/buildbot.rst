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

The preferred way is to use an nginx reverse proxy, since nginx is used for the apt server later on.

Using nginx
-----------

Install nginx::

  sudo apt-get install nginx

Edit the vhost ``/etc/nginx/sites-available/vhost-buildbot.conf``::

  server {
    listen 80;
    server_name buildbot.okfn.org;
  
    access_log /var/log/nginx/buildbot-error.log;
    error_log /var/log/nginx/buildbot-error.log;
  
    location / {
      proxy_pass         http://127.0.0.1:8010/;
    }
  }

Enable it::

  ln -s /etc/nginx/sites-available/vhost-buildbot.conf /etc/nginx/sites-enabled/vhost-buildbot.conf

Restart nginx::

  sudo /etc/init.d/nginx restart


Using apache
------------

Otherwise it is best to do a reverse proxy. 

For apache, edit this file::

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


Using iptables
--------------

If there is no other web service on this machine, you might connect up the addresses using iptables::

  sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8010

Virtual Machine 
===============

Set-up a virtual machine in the /home/buildslave/Vms directory, as per :doc:`vm.rst`.

It is useful to have the following scripts in the same directory too. Note buildslave user needs to be given passwordless sudo access for these to work.

start-kvm.sh
------------

::

  pidfile="/tmp/vm.pid"
  
  if pidof kvm | grep [0-9] > /dev/null
  then 
          echo ERROR: KVM process is already running
          exit 1
  fi
  
  /home/buildslave/Vms/kvm.sh $* -pidfile $pidfile &
  
  # check if the pid file created successfully
  if [ ! -f ${pidfile} ]
  then
      sleep 5
  fi
  if [ ! -f ${pidfile} ]
  then
      echo ERROR: PID file not created
      exit 1
  fi
  
  # check if the process started successfully
  if [ ! -d /proc/`sudo cat ${pidfile}` ]
  then
      echo ERROR: Process did not start properly
      exit 1
  fi

start.sh
--------

::

  #!/bin/bash
  
  if [ "X$1" = "X" ] || [ "X$2" = "X" ]  || [ "X$3" = "X" ] || [ "X$4" = "X" ]  || [ "X$5" = "X" ]; then
      echo "ERROR: call this script with network device name, tunnel name, amount of memory, number of CPUs and path to the image e.g." 
      echo "       $0 eth0 qtap0 512M 4 /home/Vms/ckan_2/tmpKfAdeU.qcow2 [extra args to KVM]"
      exit 1
  fi
  
  NETWORK_DEVICE=$1
  TUNNEL=$2
  MEM=$3
  CPUS=$4
  IMAGE=$5
  EXTRA=$6
  MACADDR="52:54:$(dd if=/dev/urandom count=1 2>/dev/null | md5sum | sed 's/^\(..\)\(..\)\(..\)\(..\).*$/\1:\2:\3:\4/')";
  
  echo "Creating bridge..."
  sudo iptables -t nat -A POSTROUTING -o ${NETWORK_DEVICE} -j MASQUERADE
  sudo brctl addbr br0
  sudo ifconfig br0 192.168.100.254 netmask 255.255.255.0 up
  echo "done."
  echo "Creating tunnel..."
  sudo modprobe tun
  sudo tunctl -b -u root -t ${TUNNEL}
  sudo brctl addif br0 ${TUNNEL}
  sudo ifconfig ${TUNNEL} up 0.0.0.0 promisc
  echo "done."
  echo "Starting VM ${IMAGE} on ${TUNNEL} via ${NETWORK_DEVICE} with MAC ${MACADDR}..."
  sudo /usr/bin/kvm -M pc-0.12 -enable-kvm -m ${MEM} -smp ${CPUS} -name dev -monitor pty -boot c -drive file=${IMAGE},if=ide,index=0,boot=on -net nic,macaddr=${MACADDR} -net tap,ifname=${TUNNEL},script=no,downscript=no -serial none -parallel none -usb ${EXTRA}

stop-kvm.sh
-----------

::

  #! /bin/bash
  
  pidfile="/tmp/vm.pid"
  
  pid2kill=`sudo cat $pidfile`
  if ! pidof kvm | grep [0-9] > /dev/null
  then   
          echo KVM process is not running
  else
          echo Killing process $pid2kill
          sudo kill -9 $pid2kill
  fi
  
  if [ ! -e "$pidfile" ]
  then   
          echo "No process file: $pidfile"
  else
          sudo rm $pidfile
  fi


apt server for tests
====================

The buildbot server is setup as an apt server, so that the process of installing a deb package can be tested.

The basic way to do this is documented here: http://joseph.ruscio.org/blog/2010/08/19/setting-up-an-apt-repository/ but we vary this. For example, for tests we don't sign the packages with a key (it is difficult to type the passphrase from a script).

::

  sudo apt-get install reprepro
  sudo mkdir -p /var/packages
  sudo chown okfn:okfn /var/packages
  mkdir -p /var/packages/ubuntu_ckan-test/conf
  touch /var/packages/ubuntu_ckan-test/conf/override.lucid

Create the configuration ``/var/packages/ubuntu_ckan-test/conf/distributions`` as::

  Origin: Open Knowledge Foundation
  Label: Open Knowledge Foundation
  Codename: lucid
  Architectures: amd64
  Components: universe
  Description: CKAN APT Repository
  DebOverride: override.lucid
  DscOverride: override.lucid

Create the reprepro options file ``/var/packages/ubuntu_ckan-test/options`` as::

  verbose
  basedir .

Get permissions right::

  sudo chown -R buildslave:buildslave /var/packages/ubuntu_ckan-test

Install nginx::
  
  sudo apt-get install nginx

Here we configure the name of the server as apt.okfn.org by creating /etc/nginx/sites-available/vhost-packages.conf::

  server {
    listen 80;
    server_name dgu-buildbot.okfn.org;
  
    access_log /var/log/nginx/packages-error.log;
    error_log /var/log/nginx/packages-error.log;
  
    location / {
      root /var/packages;
      index index.html;
    }
  
    location ~ /(.*)/conf {
      deny all;
    }

    location ~ /(.*)/db {
      deny all;
    }
  }

Configure the hash bucket size by creating the file /etc/nginx/conf.d/server_names_hash_bucket_size.conf::

  server_names_hash_bucket_size 64;

Enable the APT server::

  cd /etc/nginx/sites-enabled
  sudo ln -s ../sites-available/vhosts-packages.conf .
  sudo /etc/init.d/nginx restart
