SSH Tunnels
===========

Simple script to enable ssh tunnels automatically using systemd


Requirements:
=============

* systemd 
* autossh 
* perl

For debian: 
apt-get install autossh

Installation:
=============

To deploy new ssh tunnels you should, first:
* Decide which server should initiate the tunnel
* Check on both server which tcp ports are availables
* Choose on eport for each server

Then, on the tunnel initiating server:
* install git and autossh: `apt-get install git autossh`
* install perl dependencies: `cpan install Config::Auto`
* clone the repository in /usr/local: `cd /usr/local; git clone https://github.com/aziugo/ssh_tunnels.git`
* create a specific user: `adduser --system --home /home/ssh-tunnel ssh-tunnel`
* create an ssh key for the ssh-tunnel user WITHOUT passphrase: `su -l ssh-tunnel -s /bin/bash -c "ssh-keygen -t rsa -b 4096"`
* copy the service file in the system: `cp /usr/local/ssh_tunnels/ssh_tunnel@.service /etc/systemd/system`
* edit the files and folder in `/usr/local/ssh_tunnels/etc`

On the other server you should:
* create a specific user: `adduser --system --home /home/ssh-tunnel ssh-tunnel`
* add the public key (located in /home/ssh-tunnel/.ssh/id_rsa.pub on the first server) in /home/ssh-tunnel/.ssh/authorized_keys

When this is ready, on the first server, launch the service with: `systemctl start ssh_tunnel@MY_SECOND_SERVER`
You can check if everything works using `systemctl status ssh_tunnel@MY_SECOND_SERVER` or using `lsof -i tcp`

