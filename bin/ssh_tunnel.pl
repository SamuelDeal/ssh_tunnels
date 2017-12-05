#!/usr/bin/env perl

use strict;
use warnings;
use v5.22.1;

use Config::Auto;
use Getopt::Long;
use Pod::Usage;
use File::Basename;
use Socket;
use Data::Dumper;

no warnings "experimental::lexical_subs";
use feature 'lexical_subs';

use constant DEFAULT_CONFIG_FILE => "/etc/ssh_tunnel/ssh_tunnel.conf";

my sub trim;
my sub is_abs;
my sub count_substr;

sub main {
    my $help = 0;
    my $man = 0;
    my $config_file = DEFAULT_CONFIG_FILE;
    my $all = 0;
    
    GetOptions(
        'm|man!'          => \$help,
        'h|?|help!'       => \$man,
        'config|c=s'      => \$config_file,
        'a|all'			  => \$all
        
    ) or do {
        return pod2usage(-verbose => 1, -exitval => 1)
    };
    return pod2usage(-verbose => 1, -exitval => 0) if $help;
    return pod2usage(-verbose => 2, -exitval => 0) if $man;

	if(! -e $config_file) {
		print STDERR "Unable to load config file '$config_file'\n";
		exit 1;
	}
    
    my @conf = @{ load_conf(Cwd::abs_path($config_file)) };
	my @all_server_list = map($_->{'  server name'}, @conf);
	
    my @server_list = ();
    if($all) {
		@server_list = @all_server_list;
	}
	elsif(scalar(@ARGV) < 1) {
		print STDERR "You should provide at least one server name\n";
		return pod2usage(-verbose => 1, -exitval => 1);
	}
	else {
		foreach my $server (@ARGV) {
			if(! grep { /^\Q$server\E$/ } @all_server_list) {
				print STDERR "Unknown server '$server' in config\n";
				exit 1;
			}						
		}
		@server_list = @ARGV;
	}
	
	my @used_tunnel_list = ();
	foreach my $tunnel_conf (@conf) {
		my $server = $tunnel_conf->{'  server name'};
		push @used_tunnel_list, $tunnel_conf if grep { /^\Q$server\E$/ } @server_list;
	}
	exit run(@used_tunnel_list);
}

sub load_conf {
	my ($config_file,) = @_;
	
	my $path = Cwd::abs_path(dirname($config_file));
	
	chdir $path;
	my $config_content = load_conf_content(Cwd::abs_path(basename($config_file)));
	my $config = parse_conf($config_content);

	my @tunnel_list = ();
	
	foreach my $server (sort keys %{ $config }) {
		my $found = 0;
		foreach my $key (sort keys %{ $config->{$server} }) {
			next if ref($config->{$server}->{$key}) eq "";
			$found = 1;
			$config->{$server}->{$key}->{'  server name'} = $server;
			$config->{$server}->{$key}->{'  conf name'} = "$server/$key";
			push @tunnel_list, $config->{$server}->{$key};
		}
		
		if(!$found) {
			$config->{$server}->{'  server name'} = $server;
			$config->{$server}->{'  conf name'} = $server;
			push @tunnel_list, $config->{$server};
		}
	}
	
	my @local_port_list = ();
	my %remote_port_list = ();
	
	foreach my $conf (@tunnel_list) {
		my $conf_name = $conf->{'  conf name'};
		my $server = $conf->{'  server name'};
		
		die "Invalid config for '$conf_name' server: no key defined\n" unless exists $conf->{'key'};
		die "Invalid config for '$conf_name' server: the key doesn't exists\n" unless -e $conf->{'key'};
		die "Invalid config for '$conf_name' server: no user defined\n" unless exists $conf->{'user'};
		
		die "Invalid config for '$conf_name' server: no local_port defined\n" unless exists $conf->{'local_port'};
		die "Invalid config for '$conf_name' server: bad local_port defined\n" unless $conf->{'local_port'} =~ /^[0-9]+$/;
		my $local_port = $conf->{'local_port'};
		die "Invalid config for '$conf_name' server: local port $local_port already defined\n" if grep( /^\Q$local_port\E$/, @local_port_list);
		
		die "Invalid config for '$conf_name' server: no remote_port defined\n" unless exists $conf->{'remote_port'};
		die "Invalid config for '$conf_name' server: bad remote_port defined\n" unless $conf->{'remote_port'} =~ /^[0-9]+$/;
		my $remote_port = $conf->{'remote_port'};
		if((exists $remote_port_list{$server}) && grep( /^\Q$remote_port\E$/, @{ $remote_port_list{$server}})) {
			die "Invalid config for '$conf_name' server: remote port $remote_port already used\n";
		}
		$conf->{'reverse'} = 0 unless exists $conf->{'reverse'};
		push @local_port_list, $local_port;
		$remote_port_list{$server} = [] unless exists $remote_port_list{$server};
		push @{ $remote_port_list{$server} }, $remote_port;
	}
	
	return \@tunnel_list;
}

sub parse_conf {
	my ($config_content,) = @_;
	
	my %config = %{ Config::Auto::parse($config_content) };
	
	# Apply inheriting from global
	if(exists $config{'global'}) {
		foreach my $server (keys %config) {
			next if $server eq 'global';
			foreach my $key (keys %{ $config{'global'} }) {
				$config{$server}->{$key} = $config{'global'}->{$key} unless exists $config{$server}->{$key};
			}
		}
		delete $config{'global'};
	}
	
	# Manage server name from first config level
	foreach my $server (grep { ! /\// } keys %config) {
		my $server_realname = undef;
		if(exists $config{$server}{'server'}) {
			my $server_realname = $config{$server}->{'server'};
			gethostbyname($server_realname) or die "Can't resolve $server_realname: $!\n";
		}
		else {
			$server_realname = $server;
			gethostbyname($server_realname) or die "Can't resolve $server_realname: $!\n".
				"Please define a 'server' key in configuration\n";
		}
		$config{$server}->{'server_realname'} = $server_realname;
		$config{$server}->{'server_ip'} = inet_ntoa(scalar(gethostbyname($server_realname)) || 'localhost');
	}
	
	# Manage hierarchical config
	my @subkeys = grep { $_ ne 'global' } grep { /\// } keys %config;
	@subkeys = sort {
		my $result = count_substr("/", $a) cmp count_substr("/", $b);
		return $result unless $result == 0;
		return $a cmp $b;
	} @subkeys;
	foreach my $subkey (@subkeys) {
		my @parts = split /\//, $subkey;
		my $base = $config{shift @parts};
		foreach my $part (@parts) {
			$base->{$part} = {} unless exists $base->{$part};
			foreach my $key (keys %{ $base }) {
				next unless ref($base->{$key}) eq "";
				$base->{$part}->{$key} = $base->{$key} unless exists $base->{$part}->{$key};
			}
			$base = $base->{$part};
		}
		foreach my $key (keys %{ $config{$subkey} }) {
			$base->{$key} = $config{$subkey}->{$key};
		}
	}
	foreach my $subkey (grep { /\// } @subkeys) {
		delete $config{$subkey};
	}	
	delete $config{'global'} if exists $config{'global'};
	return \%config;
}

sub load_conf_content {
	my ($config_file,) = @_;
	
	open my $fh, "<", $config_file or die "could not open '$config_file': $!\n";
	my $result = '';
	
	while(my $line = <$fh>) {
		next if $line =~ /^#/ or $line =~ /^\s*$/;
		($line,) = split(/#/, $line) if $line =~ /#/;
		
		if($line =~ /^\s*include\s+(.*)$/) {
			my $include = trim $1;
			$include = substr($include, 1 -1) if $include =~ /^".*"$/ or $include =~ /^'.*'$/;

			foreach my $included ( grep {-e} glob($include) ) {
				my $file_content = "";
				eval {
					my $server = basename($included);
					$server =~ s/\.[^.]+$//;
					$file_content = load_conf_content($included);
					Config::Auto::parse($file_content); # Check the syntax of the included file
					$file_content =~ s/\[([^\]]+)\]/[$server\/$1]/g;
					$result .= "\n[$server]\n$file_content\n";
					1;
				} or do {
					print STDERR "Invalid config file '$included': $!\n";
					next;
				};
			}
		}
		else {
			$result .= $line;
		}
	}	
	close $fh;	
	Config::Auto::parse($result);  # Check the syntax of the all file to be sure	
	return $result;
}

sub run {
    my @tunnel_list = @_;
    
    # Sorting tunnels by proc to launch
    my @proc_conf_list = ();
    foreach my $tunnel (@tunnel_list) {
		my $found = 0;
		foreach my $proc_info (@proc_conf_list) {
			if($proc_info->{'key'} eq $tunnel->{'key'} && $proc_info->{'server_ip'} eq $tunnel->{'server_ip'} && 
						$proc_info->{'user'} eq $tunnel->{'user'}) {
				$found = 1;
				push @{ $proc_info->{'list'} }, $tunnel;
				last;
			}			
		}
		if(!$found) {
			push @proc_conf_list, {
				'key' => $tunnel->{'key'},
				'server_ip' => $tunnel->{'server_ip'},
				'user' => $tunnel->{'user'},
				'list' => [$tunnel]
			};		
		}
	}
	
	# Generate proc command
	my @proc_cmd_list = ();
	my $autossh_path = qx/which autossh/;
	chomp($autossh_path);
	foreach my $proc_conf (@proc_conf_list) {
		my @cmd = ($autossh_path, "-M", "0", "-nNT", "-o", 'ServerAliveInterval 60', "-o", 
			'ServerAliveCountMax 3', '-i', $proc_conf->{'key'}, '-l', $proc_conf->{'user'}, 
			$proc_conf->{'user'}."@".$proc_conf->{'server_ip'});
		foreach my $tunnel_port (@{ $proc_conf->{'list'} }) {
			if($tunnel_port->{'reverse'}) {
				push @cmd, '-R';
				push @cmd, $proc_conf->{'server_ip'}.':'.$tunnel_port->{'remote_port'}.':127.1.1.1:'.$tunnel_port->{'local_port'};
			}
			else {
				push @cmd, '-L';
				push @cmd, '127.1.1.1:'.$tunnel_port->{'local_port'}.':'.$proc_conf->{'server_ip'}.':'.$tunnel_port->{'remote_port'};
			}
		}
		
		push @proc_cmd_list, \@cmd;
	}	
	
	# Run commands
	my @alived = ();
	foreach my $proc_cmd (@proc_cmd_list) {
		my $pid = fork();
		die "Unable to fork: $!\n" unless defined $pid;
		
		if($pid == 0) {
			print join(' ', map { "'".$_."'" } @{$proc_cmd})."\n";
			exec @{$proc_cmd} or die "couldn't exec autossh: $!";
		}
		else {
			push @alived, $pid;
		}
	};
	
	# Wait for all process to finish
	my $exit_code = 0;
	while(1) {
		my $child_exit_code = wait();
		return $exit_code if $child_exit_code == -1;
		if($exit_code > 0) {
			print STDERR "Child exit with code $?\n";
			$exit_code = 1;
		}		
	}
}

sub is_abs {
    my ($filepath) = @_;

    if($^O =~ /Win/ ){  # Windows
        return $filepath =~ /^[A-Z]:\\/;  
    }
    else { # we suppose *nix oses
        return $filepath =~ /^\//;
    }
}

sub trim {
    my @out = grep { defined($_) } @_;
    for(@out) {
        s/^\s+//;
        s/\s+$//;
    }
    return wantarray ? @out : $out[0];
}

sub count_substr {
	my ($needle, $haystack,) = @_;
	my $c = () = $haystack =~ /\Q$needle\E/g;
	return $c;	
}

main();

__END__

=head1 NAME

GDC.pl - Git Deployer Client

=head1 SYNOPSIS
GDC.pl PROJECT BRANCH
 Options:
   --help, -h           brief help message
   --man, -m            full documentation
   PROJECT              the git repository name
   BRANCH               the branch updated

=head1 OPTIONS
=over 8
=item B<--help>
Print a brief help message and exits.
=item B<-man>
Prints the manual page and exits.
=back

=head1 DESCRIPTION
B<This program> will read the given input file(s) and do something
useful with the contents thereof.
=cut

