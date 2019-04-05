SSH Tunnels
===========

Simple script to enable ssh tunnels automatically using systemd


TL;DR
-----

```
REMOTE_SERVER=my.domain.tld

sh debian_install.sh

echo "[$REMOTE_SERVER]" >> /usr/local/sshtunnel/sshconfig.conf
echo "local_port=888" >> /usr/local/sshtunnel/sshconfig.conf
echo "remote_port=999" >> /usr/local/sshtunnel/sshconfig.conf

ssh "$REMOTE_SERVER" sudo bash -c "adduser --system --home /usr/local/sshtunnel ssh-tunnel 2> /dev/null"
ssh "$REMOTE_SERVER" sudo bash -c "mkdir -p /usr/local/sshtunnel/.ssh"
ssh "$REMOTE_SERVER" sudo bash -c "touch /usr/local/sshtunnel/.ssh/authorized_keys"
ssh "$REMOTE_SERVER" sudo bash -c "chown -R ssh-tunnel:nogroup /usr/local/sshtunnel/.ssh"
ssh "$REMOTE_SERVER" sudo bash -c "chmod 700 ssh-tunnel:nogroup /usr/local/sshtunnel/.ssh"
ssh "$REMOTE_SERVER" sudo bash -c "chmod 600 ssh-tunnel:nogroup /usr/local/sshtunnel/.ssh/authorized_keys"

sudo cat /usr/local/sshtunnel/.ssh/id_rsa.pub | ssh "$REMOTE_SERVER" -T "sudo cat >> /usr/local/sshtunnel/.ssh/authorized_keys"

systemctl start "sshtunnel@$REMOTE_SERVER"
systemctl enable "sshtunnel@$REMOTE_SERVER"
```

Presentation:
-------------

This script aims to provide an easy way to manage ssh tunnels on linux servers, using a comprehensive configuration scheme and **SystemD** for system integration.

The real job is done by the amazing **autossh** and **open-ssh** tools

This script should be compatible with **python 2** and **python 3**

It is designed to have a very low requirements


Usage:
------

* To start a configured tunnel: ```systemctl start sshtunnel@my.domain.tld```

* To see what is running: ```sshtunnel status```

* To see what is configured: ```sshtunnel config```

* For more options: ```sshtunnel --help```


Requirements:
-------------

* python 2 or 3
* autossh 
* ssh-client
* some classic unix tools (ps, pidof, lsof)
* systemd


Installation:
-------------

To deploy new ssh tunnels you should, first:
* Decide which server should initiate the tunnel
* Check on both server which tcp ports are availables
* Choose on port for each server

Then, on the tunnel initiating server, download this repository and 
* Run the ```debian_install.sh``` 
* or install it mannually:
  * install requirements (mainly autossh): `apt-get install autossh ssh-client python3 lsof procps`
  * create a specific user: `adduser --system --home /usr/local/sshtunnel ssh-tunnel`
  * copy src/sshtunnel.py where you want: `cp src/sshtunnel.py /usr/local/sshtunnel/`
  * create an ssh key for the ssh-tunnel user WITHOUT passphrase: `su -l ssh-tunnel -s /bin/bash -c "ssh-keygen -t rsa -b 4096 -N''"`
  * copy the service file in the system: `cp conf_examples/sshtunnel@.service /etc/systemd/system`
  * create the configuration you want (the default config file is sshtunnel.conf)

On the other server you should:
* create a specific user: `adduser --system --home /usr/local/ssh-tunnel ssh-tunnel`
* add the public key (located in /usr/local/ssh-tunnel/.ssh/id_rsa.pub on the first server) in /home/ssh-tunnel/.ssh/authorized_keys

When this is ready, on the first server, launch the service with: `systemctl start ssh_tunnel@MY_SECOND_SERVER`
You can check if everything works using `systemctl status ssh_tunnel@MY_SECOND_SERVER` or using `lsof -i TCP`

Configuration:
--------------

Here a list of fields you can specify for a tunnel:

### Required fields:

* **local_port**: The local port used to established the connection. 
* **remote_server**: The remote server to connect to
* **remote_port**: The tunnel port on the remote server

### Optional fields:

* **reverse**: Do you want a reverse tunnel? Optional, default `False`
* **name**: The name of the tunnel. Optional: It can also be the name of the ini section
* **group_name**: A string to group several tunnels, to more easily start and stop them. Optional: It can also be deduced from the section name
* **local_address**: The local address where the ssh tunnel starts. Optional: default is `127.1.1.1`
* **ssh_user**: The remote ssh user. Optional, default is the current user
* **ssh_key**: The ssh key used to connect to remote server. Optional, default is ssh default
* **ssh_port**: The remote server sshd port. Optional, default is `22`
* **ssh_options**: options Optional, default: `-n -o ServerAliveInterval=60 -o ServerAliveCountMax=3`


Todo:
-----

* Not tested enough
* Implement remote ssh tunnel detection 
* Improve output formatting
* Check stderr is a tty


