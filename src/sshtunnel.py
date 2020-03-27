#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set tabstop=4:softtabstop=4:shiftwidth=4:expandtab:textwidth=120

"""
This script aims to provide an easy way to manage ssh tunnels on linux servers,
using a comprehensive configuration scheme and SystemD for system integration.

The real job is done by the amazing autossh and ssh tools

This script should be compatible with python 2 and python 3
"""

__author__ = "Samuel Déal"
__copyright__ = "Copyright 2019, Aziugo SAS"
__credits__ = ["Samuel Déal"]
__license__ = "GPL"
__version__ = "0.9.0"
__maintainer__ = "Samuel Déal"
__status__ = "Development"


# Python core libs
import sys
import os
import collections
import logging
import logging.handlers
import subprocess
import signal
import datetime
import argparse
import tempfile
import contextlib
import re
import glob
import copy
import platform
import time
import getpass
import shlex
import socket
import threading

script_path = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
log = logging.getLogger("sshtunnel")


# Python 2/3 compatibility mapping
# ----------------------------------------------------------------------------
if sys.version_info[0] == 2:  # Python 2 version
    import ConfigParser
    import StringIO

    configparser = ConfigParser
    io = StringIO

    def is_string(var):
        """
        Check if the var is a string

        :param var:     The variable to test
        :type var:      any
        :return:        True if the variable is a kind of string
        :rtype:         bool
        """
        return isinstance(var, basestring)

    def is_primitive(var):
        """
        Check if the var is a primitive (aka scalar) var (like string, int, float, etc...)

        :param var:     The variable to test
        :type var:      any
        :return:        True if the variable's type is a primitive type
        :rtype:         bool
        """
        return isinstance(var, (basestring, int, long, bool, float))

    def is_PathLike(var):
        """
        Does the input is a os.PathLike object?

        :param var:     The variable to test
        :type var:      any
        :return:        True if the variable's type is os.PathLike
        :rtype:         bool
        """
        return False

    def to_bytes(var):
        """
        Convert a var to a byte string

        :param var:     The variable to convert
        :type var:      any
        :return:        The var converted to byte string
        :rtype:         str
        """
        if isinstance(var, str):
            return var
        elif isinstance(var, unicode):
            return var.encode("UTF-8")
        else:
            return str(var)

    def to_unicode(var):
        """
        Convert a var to a unicode string

        :param var:     The variable to convert
        :type var:      any
        :return:        The var converted to string
        :rtype:         unicode
        """
        if isinstance(var, unicode):
            return var
        elif isinstance(var, str):
            return var.decode("UTF-8")
        else:
            return str(var).decode("UTF-8")

    def to_str(var):
        """
        Convert a var to a string

        :param var:     The variable to convert
        :type var:      any
        :return:        The var converted to string
        :rtype:         str
        """
        return to_bytes(var)

    def first(dict_var):
        """
        Get first key of a dictionary

        :param dict_var:    A non empty dictionary
        :type dict_var:     dict[any, any]
        :return:            The first key and value of the input var
        :rtype:             tuple[any, any]
        """
        return dict_var.iteritems().next()

    def shell_quote(arg):
        """
        Quote a parameter for shell usage
        Example:
            shell_quote("it's a cool weather today") => 'it'"'"'s a cool weather today'

        :param arg:     The argument to quote, required
        :type arg:      str|unicode
        :return:        The quoted argument
        :rtype:         str
        """
        import pipes
        return pipes.quote(arg)

    def check_ini_content(content, filename=None):
        """
        Check if the content input is a valid ini file
        Raise an error if it is not valid

        :param content:     The content to check
        :type content:      str
        :param filename:    The name of the file the content comes from (optional, default None)
        :type filename:     str|None
        :raise:             Error if the content is not a valid ini file
        """
        with temp_file(content) as tmp_file:
            with open(tmp_file, "r") as fh:
                configparser.ConfigParser().readfp(fh, filename)

    def configparser_get(parser, section, option, fallback):
        """
        Get a value from config parser, with default

        :param parser:      The parser to read the data from
        :type parser:       ConfigParser.ConfigParser
        :param section:     The section name
        :type section:      str
        :param option:      The option to read
        :type option:       str
        :param fallback:    The value to return if the parser does'nt have the specified option
        :type fallback:     any
        :return:            The value of the parser if it has it, the fallback param otherwise
        :rtype:             any
        """
        if not parser.has_section(section):
            return fallback
        return parser.get(section, option) if parser.has_option(section, option) else fallback


    def configparser_from_str(content, filename=None):
        """
        Generate a configParser instance which has read the given content

        :param content:         The content to fill
        :type content:          str
        :param filename:        The file the content came from. Optional, default None
        :type filename          str|None
        :return:                A ConfigParser instance already initialized
        :rtype:                 ConfigParser.ConfigParser
        """
        fp = io.StringIO(content)
        parser = configparser.ConfigParser()
        parser.readfp(fp, filename)
        return parser


else:  # Python 3 version
    import configparser
    import io

    StandardError = Exception

    def is_string(var):
        """
        Check if the var is a string

        :param var:     The variable to test
        :type var:      any
        :return:        True if the variable is a kind of string
        :rtype:         bool
        """
        return isinstance(var, str)

    def is_primitive(var):
        """
        Check if the var is a primitive (aka scalar) var (like string, int, float, etc...)

        :param var:     The variable to test
        :type var:      any
        :return:        True if the variable's type is a primitive type
        :rtype:         bool
        """
        return isinstance(var, (str, int, bool, float, bytes))

    def is_PathLike(var):
        """
        Does the input is a os.PathLike object?

        :param var:     The variable to test
        :type var:      any
        :return:        True if the variable's type is os.PathLike
        :rtype:         bool
        """
        return isinstance(var, os.PathLike)

    def to_bytes(var):
        """
        Convert a var to a byte string

        :param var:     The variable to convert
        :type var:      any
        :return:        The var converted to byte string
        :rtype:         bytes
        """
        if isinstance(var, bytes):
            return var
        elif isinstance(var, str):
            return var.encode("UTF-8")
        else:
            return str(var).encode("UTF-8")

    def to_unicode(var):
        """
        Convert a var to a unicode string

        :param var:     The variable to convert
        :type var:      any
        :return:        The var converted to string
        :rtype:         str
        """
        if isinstance(var, str):
            return var
        elif isinstance(var, bytes):
            return var.decode("UTF-8")
        else:
            return str(var)

    def to_str(var):
        """
        Convert a var to a string

        :param var:     The variable to convert
        :type var:      any
        :return:        The var converted to string
        :rtype:         str
        """
        return to_unicode(var)

    def first(dict_var):
        """
        Get first key of a dictionary

        :param dict_var:    A non empty dictionary
        :type dict_var:     dict[any, any]
        :return:            The first key and value of the input var
        :rtype:             tuple[any, any]
        """
        return next(iter(dict_var.items()))

    def shell_quote(arg):
        """
        Quote a parameter for shell usage
        Example:
            shell_quote("c'est cool aujourd'hui, il fait beau") => 'c'"'"'est cool aujourd'"'"'hui, il fait beau'

        :param arg:        String, the argument to quote, required
        :return:        String, the quoted argument
        """
        return shlex.quote(arg)

    def check_ini_content(content, filename=None):
        """
        Check if the content input is a valid ini file
        Raise an error if it is not valid

        :param content:     The content to check
        :type content:      str
        :param filename:    The name of the file the content comes from (optional, default None)
        :type filename:     str|None
        :raise:             Error if the content is not a valid ini file
        """
        configparser.ConfigParser().read_string(content, filename)

    def configparser_get(parser, section, option, fallback):
        """
        Get a value from config parser, with default

        :param parser:      The parser to read the data from
        :type parser:       ConfigParser.ConfigParser
        :param section:     The section name
        :type section:      str
        :param option:      The option to read
        :type option:       str
        :param fallback:    The value to return if the parser does'nt have the specified option
        :type fallback:     any
        :return:            The value of the parser if it has it, the fallback param otherwise
        :rtype:             any
        """
        return parser.get(section, option, fallback=fallback)

    def configparser_from_str(content, filename=None):
        """
        Generate a configParser instance which has read the given content

        :param content:         The content to fill
        :type content:          str
        :param filename:        The file the content came from. Optional, default None
        :type filename          str|None
        :return:                A ConfigParser instance already initialized
        :rtype:                 configparser.ConfigParser
        """
        fp = io.StringIO(content)
        parser = configparser.ConfigParser()
        parser.read_file(fp, source=filename)
        return parser


# Other utility definitions
# ----------------------------------------------------------------------------

def is_array(var):
    """
    Check if the input is a valid array, but not a string nor a dict

    :param var:     The input to test
    :type var:      any
    :return:        True if var is an array
    :rtype:         bool
    """
    if is_primitive(var):
        return False
    if isinstance(var, dict):
        return False
    return isinstance(var, collections.Iterable)


def is_dict(var):
    """
    Check if the input is a valid dict

    :param var:     The input to test
    :type var:      any
    :return:        True if var is a dictionary
    :rtype:         bool
    """
    return isinstance(var, dict)


def ll_int(var):
    """
    Does the input looks like an int ?

    :param var:     The input to test
    :type var:      any
    :return:        True if the input looks like a valid int
    :rtype:         bool
    """
    try:
        int(var)
        return True
    except ValueError:
        return False


def ll_float(var):
    """
    Check parameter can be cast as a valid float

    :param var:     The variable to check
    :type var:      any
    :return:        True if the value can be cast to float
    :rtype:         bool
    """
    try:
        float(var)
        return True
    except (ValueError, TypeError):
        return False


def ll_bool(value):
    """
    Check if value looks like a bool

    :param value:       The value to check
    :type value:        any
    :return:            The boolean value
    :rtype:             bool
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if ll_float(value):
        return int(float(value)) in (0, 1)
    try:
        value = str(value)
    except StandardError:
        return False
    if value.lower() in ('yes', 'true', 't', 'y', '1', 'o', 'oui', 'on'):
        return True
    elif value.lower() in ('no', 'false', 'f', 'n', '0', 'non', 'off'):
        return True
    else:
        return False


def to_bool(value):
    """
    Convert a string to bool
    Raise error if not a valid bool

    :param value:       The value to cast
    :type value:        any
    :return:            The boolean value
    :rtype:             bool
    """
    if value is None:
        raise TypeError("Not a boolean")
    if isinstance(value, bool):
        return value
    if ll_float(value):
        if not int(float(value)) in (0, 1):
            raise TypeError("Not a boolean")
        return int(float(value)) == 1
    try:
        value = str(value)
    except StandardError:
        raise TypeError("Not a boolean")
    if value.lower() in ('yes', 'true', 't', 'y', '1', 'o', 'oui', 'on'):
        return True
    elif value.lower() in ('no', 'false', 'f', 'n', '0', 'non', 'off'):
        return False
    else:
        raise TypeError("Not a boolean")


def unique(var):
    """
    Return a list without any doublon

    :param var:     A list to clean
    :type var:      list
    :return:        A list without doublons
    :rtype:         list
    """
    return sorted(list(set(var)))


def index_by(array, key):
    """
    Reorganize given array inside a dict

    :param array:       A list to organize
    :type array:        list[any]
    :param key:         Key by which you want to organize your array
    :type key:          str|callable
    :return:            A dictionary with the key as index and a list as value
    :rtype:             dict[any, list[any]]
    """
    results = {}
    for element in array:
        if callable(key):
            new_key = key(element)
        else:
            new_key = getattr(element, key)
        if new_key not in results.keys():
            results[new_key] = []
        results[new_key].append(element)
    return results


def indent(some_str=None, indent_first=True, indent_str="  "):
    """
    Indent a given input text

    :param some_str:        The input to indent. Optional, default None
    :type some_str:         str|None
    :param indent_first:    Do you want start by an indent or indent only the subsequent lines ? Optional, default True
    :type indent_first:     bool
    :param indent_str:      The string used as indentation. Optional default "  "
    :type indent_str:       str
    :return:                The indented text
    :rtype:                 str
    """
    if some_str is None:
        return indent_str
    if indent_first:
        return os.linesep.join([indent_str+line for line in to_str(some_str).splitlines()])
    else:
        return (os.linesep+indent_str).join([line for line in to_str(some_str).splitlines()])


@contextlib.contextmanager
def using_cwd(path):
    """
    Change the current directory. Should be used using the `with` keyword.
    It yield and then restore the previous current directory

    :param path:    The path you want to use as new current directory
    :type path:     str
    """
    current_cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(current_cwd)


@contextlib.contextmanager
def temp_file(content, suffix="", prefix="tmp", dir=None):
    """
    Generate a temporary file, and put the content inside it
    It yield the file path, and ensure file destruction

    :param content:     The content to put inside the temp file
    :type content:      str
    :param suffix:      The end of the name of the generated temp file. Optional, default empty string
    :type suffix:       str
    :param prefix:      The beginning of the name of the generated temp file. Optional, default "tmp"
    :type prefix:       str
    :param dir:         The place where we will create the temporary file. Optional, default None
    :type dir:          str|None
    :return:            The temporary file path
    :rtype:             str
    """
    if dir and not os.path.exists(dir):
        os.makedirs(dir)
    tmp_filename = None
    fd = None
    try:
        fd, tmp_filename = tempfile.mkstemp(suffix, prefix, dir)
        with open(tmp_filename, "w") as fh:
            fh.write(content)
            fh.flush()
        yield tmp_filename
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_filename is not None and os.path.exists(tmp_filename):
            os.remove(tmp_filename)


class TermColor(object):
    """
    Common term codes for colored output
    """

    BOLD = '\033[1m'
    OK = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    _disabled = False

    @staticmethod
    def disable():
        """ Disable coloring strings """
        TermColor._disabled = True

    @staticmethod
    def color(content, color):
        """
        Embed given text with term color escape sequences

        :param content:     The text to color
        :type content:      str
        :param color:       The color you want
        :type color:        str
        :return:            The given input between the color and the reset escape sequences
        :rtype:             str
        """
        if TermColor._disabled or not sys.stdout.isatty():
            return content
        return color+content+TermColor.ENDC


# Process management functions
# ----------------------------------------------------------------------------

def run_cmd(*cmd_args):
    """
    Run synchronously a command

    :param cmd_args:    The arguments to pass to the command
    :type cmd_args:     str
    :return:            The exit code, the stdout and stderr outputs of the command
    :rtype:             tuple[int, str, str]
    """
    pipes = subprocess.Popen([to_str(arg) for arg in cmd_args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = pipes.communicate()
    return pipes.returncode, to_str(std_out).strip(), to_str(std_err).strip()


def check_run_cmd(*cmd_args):
    """
    Run synchronously a command, and raise error in case of failure (exit code != 0)

    :param cmd_args:    The arguments to pass to the command
    :type cmd_args:     str
    :return:            The stdout output of the command
    :rtype:             str
    """
    code, out, err = run_cmd(*cmd_args)
    if code != 0:
        error = "Command failed with exit code "+to_str(code)+os.linesep
        error += "  Command: "+" ".join([shell_quote(arg) for arg in cmd_args])
        if err:
            error += os.linesep+"  Error output:"+os.linesep+indent(to_str(err), indent_str="    ")
        raise RuntimeError(error)
    return out


def wait_proc(proc, timeout):
    """
    Wait for a proc to finish for some time, without raising errors on timeout

    :param proc:        A process object to wait for
    :type proc:         subprocess.Popen
    :param timeout:     The time to wait the process to finish
    :type timeout:      int|float
    :return:            The exit code of the process, or None if the process is still running
    :rtype:             int|None
    """
    if timeout <= 0:
        raise RuntimeError("invalid timeout value: "+repr(timeout))
    if proc.returncode is not None:
        return proc.returncode
    proc.poll()
    if proc.returncode is not None:
        return proc.returncode
    timeout = datetime.datetime.utcnow() + datetime.timedelta(seconds=timeout)
    while timeout > datetime.datetime.utcnow():
        time.sleep(0.01)
        if proc.returncode is not None:
            return proc.returncode
    return proc.poll()


def which(exec_name):
    """
    Get path of an executable
    Raise error if not found

    :param exec_name:       The binary name
    :type exec_name:        str
    :return:                The path to the executable file
    :rtype:                 str
    """
    path = os.getenv('PATH')
    available_exts = ['']
    if "windows" in platform.system().lower():
        additional_exts = [ext.strip() for ext in os.getenv('PATHEXT').split(";")]
        available_exts += ["."+ext if ext[0] != "." else ext for ext in additional_exts]
    for folder in path.split(os.path.pathsep):
        for ext in available_exts:
            exec_path = os.path.join(folder, exec_name+ext)
            if os.path.exists(exec_path) and os.access(exec_path, os.X_OK):
                return exec_path
    raise RuntimeError("Unable to find path for executable "+str(exec_name))


# Log management functions
# ----------------------------------------------------------------------------

def flush_loggers():
    """ Flush all the logging handlers """
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for logger in loggers:
        for handler in logger.handlers:
            handler.flush()


def init_log(log_output=None):
    """
    Initialize the logging of the application.
    It can configure standard stream outputs, syslog of file logging.

    :param log_output:  The output you want. stderr if None. Optional, default None
    :type log_output:   str|None
    """
    logging.getLogger().setLevel(logging.INFO)
    log.setLevel(logging.INFO)

    if log_output is None:
        log_output = "stderr"
    if log_output in ("stderr", "stdout"):
        log_file = sys.stderr if log_output == "stderr" else sys.stdout
        log_handler = logging.StreamHandler(stream=log_file)
        log_handler.setFormatter(logging.Formatter('%(message)s'))
    elif log_output == "syslog":
        log_handler = logging.handlers.SysLogHandler(address='/dev/log')
        log_handler.setFormatter(logging.Formatter('%(name)s[%(process)d]: %(levelname)s %(message)s'))
    else:
        log_handler = logging.FileHandler(log_output)
        log_handler.setFormatter(logging.Formatter('%(asctime)s: %(levelname)-7s: %(name)s - %(message)s'))
    logging.getLogger().addHandler(log_handler)
    log.addHandler(log_handler)
    log.propagate = False


class LogPipe(threading.Thread):
    """
    A Pipe like object. Every stream writen to this file will be logged line by line

    Usage:
        out_pipe = LogPipe(logging.INFO)
        try:
            subprocess.check_call(cmd, stdout=out_pipe)
        finally:
            out_pipe.close()
    """

    def __init__(self, level, logger=None):
        """
        :param level:       The log level of the message sent to this pipe. Ex: logging.INFO
        :type level:        int
        :param logger:      A logger instance. If not provided, log into root logger. Optional, default None
        :type logger:       logging.Logger|None
        """
        threading.Thread.__init__(self)
        self.daemon = False
        self.level = level
        self.fdRead, self.fdWrite = os.pipe()
        self.pipeReader = os.fdopen(self.fdRead)
        self.process = None
        self.logger = logger if logger is not None else logging.getLogger()
        self.start()

    def fileno(self):
        """
        Return the write file descriptor of the pipe

        :return:    The write file descriptor of the pipe
        :rtype:     int
        """
        return self.fdWrite

    def run(self):
        """ Main thread loop. Log every received data line by line """
        for line in iter(self.pipeReader.readline, ''):
            self.logger.log(self.level, line.strip('\n'))

        remaining = self.pipeReader.read().strip()
        if remaining:
            self.logger.log(self.level, remaining)
        self.pipeReader.close()

    def close(self):
        """ Close the write end of the pipe. """
        os.close(self.fdWrite)

    def stop(self):
        """ Stop the logging """
        self.close()

    def __del__(self):
        try:
            self.stop()
        except:  # Ignore errors, we are in the destructor
            pass
        try:
            del self.fdRead
        except:  # Ignore errors, we are in the destructor
            pass
        try:
            del self.fdWrite
        except:  # Ignore errors, we are in the destructor
            pass


class KillEventHandler(object):
    """ Static class used to force killing of the script if too many and quit signals are received."""
    INTERVAL = datetime.timedelta(seconds=1)
    EVENT_COUNT = 3

    _quit_msg = None

    @staticmethod
    def initialise():
        """ Start to listen to system signals """
        if KillEventHandler._quit_msg is not None:
            return
        KillEventHandler._quit_msg = []
        signal.signal(signal.SIGINT, KillEventHandler._on_signal)
        signal.signal(signal.SIGTERM, KillEventHandler._on_signal)

    @staticmethod
    def _on_signal(sig, frame):
        """
        PRIVATE
        Raise KeyboardInterrupt on sigint and sigterm.
        Call os._exit if more than 2 signals are received in less than a second.

        :param sig:         The signal received by this script if this class is activated
        :type sig:          int
        :param frame:       Not used
        :type frame:        any
        :return:
        """
        log.info("Signal "+to_str(sig)+" received")
        KillEventHandler._quit_msg.append(datetime.datetime.utcnow())
        if len(KillEventHandler._quit_msg) > KillEventHandler.EVENT_COUNT:
            KillEventHandler._quit_msg = KillEventHandler._quit_msg[-KillEventHandler.EVENT_COUNT:]
        if len(KillEventHandler._quit_msg) >= KillEventHandler.EVENT_COUNT:
            if KillEventHandler._quit_msg[-1] - KillEventHandler._quit_msg[0] < KillEventHandler.INTERVAL:
                log.error(os.linesep + "Hard Exit!!!!" + os.linesep)
                flush_loggers()
                os._exit(1)
                return
        raise KeyboardInterrupt()

    def __init__(self):
        raise RuntimeError("Should not be called: KillEventHandler.__init__")


# Configuration class
# ----------------------------------------------------------------------------

class ConfigError(RuntimeError):
    """ A generic error for ssh tunnel configuration issues """
    pass


class TunnelConfig(object):
    """
    Represent the configuration of the ssh tunnel program
    """
    INCLUDE_RE = re.compile(r"^\s*include[ :=]\s*(.*)\s*$", re.I)
    SECTION_RE = re.compile(r"^\s*\[(.*)\]\s*$", re.I)
    USER_RE = re.compile(r"^[a-z_]([a-z0-9_-]{0,31}|[a-z0-9_-]{0,30}\$)$")

    def __init__(self, config_file):
        """
        Load the configuration

        :param config_file:         The configuration file to load
        :type config_file:          str
        """
        self._tunnels = self._parse_config(config_file)

    @property
    def all_tunnels(self):
        """
        Get all configured tunnels

        :return:    All configured tunnels
        :rtype:     list[Tunnel]
        """
        return self._tunnels

    @property
    def server_list(self):
        """
        Get the list of all loaded servers (real names, not nicknames)

        :return:        The list of all loaded servers
        :rtype:         list[str]
        """
        return [t.remote_server for t in self._tunnels]

    def get_tunnels(self, tunnel_identifiers):
        """
        Return the list of all tunnels of given server

        :param tunnel_identifiers:      The real name of a server
        :type tunnel_identifiers:       list[str]
        :return:                        The list of all the configured tunnels of given server
        :rtype:                         list[Tunnel]
        """
        result = []
        found_identifiers = set([])
        for tunnel in self._tunnels:
            if tunnel.name in tunnel_identifiers:
                result.append(tunnel)
                found_identifiers.add(tunnel.name)
            elif tunnel.group_name in tunnel_identifiers:
                result.append(tunnel)
                found_identifiers.add(tunnel.group_name)
            elif tunnel.remote_server in tunnel_identifiers:
                result.append(tunnel)
                found_identifiers.add(tunnel.remote_server)
            elif tunnel.remote_address in tunnel_identifiers:
                result.append(tunnel)
                found_identifiers.add(tunnel.remote_address)
        not_found_identifiers = [identifier for identifier in tunnel_identifiers if identifier not in found_identifiers]
        if not_found_identifiers:
            raise RuntimeError("Unknown tunnels: "+", ".join(not_found_identifiers))
        return result

    @staticmethod
    def _parse_config(config_file):
        """
        PRIVATE
        Parse the configuration

        :param config_file:     The config file path to load
        :type config_file:      str
        :return:                The server config, and their nickname
        :rtype:                 list[Tunnel]
        """
        try:
            preprocessed = TunnelConfig._pre_process_file(config_file)
            parser = configparser_from_str(preprocessed, config_file)
            config = TunnelConfig._analyse_config(parser)
            tunnels = TunnelConfig._check_config(config)
        except ConfigError:
            raise
        except StandardError as e:
            raise ConfigError("Bad configuration file "+config_file+": "+to_str(e))
        return tunnels

    @staticmethod
    def _check_config(config):
        """
        PRIVATE
        Check and sanitise values in parsed config
        raise ConfigError if the config is bad

        :param config:          The configuration so far parsed, grouped by group name
        :type config:           dict[str, list[dict[str, any]]]
        :return:                The ssh tunnels config, and their nickname
        :rtype:                 list[Tunnel]
        """
        results = []
        for group, tunnel_config_list in config.items():
            for tunnel_config in tunnel_config_list:
                cleaned_tunnel = {
                    "reverse": False,
                    "local_address": "127.1.1.1",
                    "ssh_options": ["-n", "-o", "ServerAliveInterval=60", "-o", "ServerAliveCountMax=3"],
                    "ssh_user": None,
                    "ssh_key": None,
                    "ssh_port": 22,
                    "group_name": group,
                    "remote_server": group
                }
                tunnel_description = group + "'s "+tunnel_config["tunnel_name"] + " tunnel"
                for key, val in tunnel_config.items():
                    key = to_str(key).strip().lower()
                    if key == "reverse":
                        if not ll_bool(val):
                            raise ConfigError("Invalid value for param 'reverse' of " + tunnel_description)
                        val = to_bool(val)
                    elif key == "remote_port":
                        if not ll_int(val):
                            raise ConfigError("Invalid value for param 'remote_port' of " + tunnel_description)
                        val = int(val)
                        if 0 >= val or val > 65534:
                            raise ConfigError("Invalid value for param 'remote_port' of " + tunnel_description)
                    elif key == "local_port":
                        if not ll_int(val):
                            raise ConfigError("Invalid value for param 'local_port' of " + tunnel_description)
                        val = int(val)
                        if 0 >= val or val > 65534:
                            raise ConfigError("Invalid value for param 'local_port' of " + tunnel_description)
                    elif key == "ssh_port":
                        if not ll_int(val):
                            raise ConfigError("Invalid value for param 'ssh_port' of " + tunnel_description)
                        val = int(val)
                        if 0 >= val or val > 65534:
                            raise ConfigError("Invalid value for param 'ssh_port' of " + tunnel_description)
                    elif key == "local_address":
                        try:
                            socket.inet_aton(val)
                        except socket.error:
                            try:
                                val = socket.gethostbyname(val)
                            except StandardError:
                                raise ConfigError("Invalid local address '" + to_str(val)+"'")
                        if int(val.split(".", 2)[0]) != 127:
                            raise ConfigError("Invalid local address '" + to_str(val) + "'")
                    elif key in ("user", "ssh_user"):
                        key = "ssh_user"
                        if not TunnelConfig.USER_RE.match(val):
                            raise ConfigError("Invalid user name '" + to_str(val)+"'")
                    elif key in ("key", "ssh_key"):
                        key = "ssh_key"
                    elif key == "ssh_options":
                        val = shlex.split(val)
                    elif key == "server":
                        key = "remote_server"
                    elif key in ("group_name", "tunnel_name", "remote_server"):
                        pass  # Just to legitimate those keys as valid
                    else:
                        raise ConfigError("Unknown config option "+to_str(key))
                    cleaned_tunnel[key] = val

                # Check missing fields
                for required_key in ("remote_port", "local_port"):
                    if required_key not in cleaned_tunnel.keys():
                        raise ConfigError("Missing param '"+required_key+"' of " + tunnel_description)

                # Check server resolution
                conf_server = cleaned_tunnel["remote_server"]
                try:
                    cleaned_tunnel["remote_address"] = socket.gethostbyname(conf_server)
                except StandardError as e:
                    raise ConfigError("Unknown remote server '" + to_str(conf_server) + "': " + to_str(e))

                # Ok, save the tunnel config
                results.append(Tunnel(cleaned_tunnel))
        return results

    @staticmethod
    def _analyse_config(parser):
        """
        PRIVATE
        Generate a coherent list of tunnel configuration from parsed values while merging common values

        :param parser:      The python config parser, loaded with the input files
        :type parser:       configparser.ConfigParser
        :return:            The uncleaned and unchecked configuration so far parsed, grouped by group name
        :rtype:             dict[str, list[dict[str, any]]]
        """
        # First read common information
        common_fields = {}
        for section in parser.sections():
            if section not in ("global", "common"):
                continue
            for key in parser.options(section):
                common_fields[key] = parser.get(section, key)

        # Then read group/server specific keys
        group_fields = {}
        for section in parser.sections():
            if section in ("global", "common") or "/" in section:
                continue
            group = section
            if group not in group_fields.keys():
                group_fields[group] = copy.copy(common_fields)
            for key in parser.options(section):
                group_fields[group][key] = parser.get(section, key)

        # Then read tunnel specific keys
        tunnel_configs_by_group = {}
        for section in parser.sections():
            if section in ("global", "common") or "/" not in section:
                continue
            group, tunnel_name = section.split("/", 2)
            fields = copy.copy(group_fields[group]) if group in group_fields.keys() else {}
            fields['tunnel_name'] = tunnel_name
            if group not in tunnel_configs_by_group.keys():
                tunnel_configs_by_group[group] = []
            for key in parser.options(section):
                fields[key] = parser.get(section, key)
            tunnel_configs_by_group[group].append(fields)

        # Finally ensure anonymous tunnel for tunnel-less server
        for group, fields in group_fields.items():
            if group in tunnel_configs_by_group.keys() or len(fields.keys()) == 0:
                continue
            default_tunnel_fields = copy.copy(fields)
            default_tunnel_fields['tunnel_name'] = "default_tunnel"
            tunnel_configs_by_group[group] = [default_tunnel_fields]
        return tunnel_configs_by_group

    @staticmethod
    def _pre_process_file(filename, sub_section=None):
        """
        PRIVATE
        Read ini file, preprend the 'sub_section' prefix on each section,
        and when a 'include' directive is found, include the following
        files with the sub_section corresponding to '<filename_without_extension>/'

        Note: this method is recursive

        :param filename:        The filename to read
        :type filename:         str
        :param sub_section:     The subsection of the file to parse. Optional, default None
        :type sub_section:      str|None
        :return:                The pre-processed content of the given file
        :rtype:                 str
        """
        result = "" if sub_section is None else "[" + sub_section + "]" + os.linesep
        with open(filename, "r") as fh:
            for line in fh:
                matches = TunnelConfig.INCLUDE_RE.match(line)
                if matches:
                    with using_cwd(os.path.abspath(os.path.dirname(filename))):
                        for sub_filename in glob.glob(matches.group(1)):
                            sub_sub_section = "" if sub_section is None else sub_section+"/"
                            sub_sub_section += os.path.splitext(os.path.basename(sub_filename))[0]
                            result += os.linesep + os.linesep
                            result += TunnelConfig._pre_process_file(sub_filename.strip(), sub_sub_section)
                    continue
                if sub_section:
                    matches = TunnelConfig.SECTION_RE.match(line)
                    if matches:
                        result += "["+sub_section+"/"+matches.group(1)+"]"+os.linesep
                        continue
                result += line
        check_ini_content(result, filename)
        return result


# Global cache classes
# ----------------------------------------------------------------------------

class LsofCache(object):
    """
    Static class to read open ports opened by ssh and sshd commands.

    Note that it raise errors for non-root users because of lsof usage
    """
    _cache = None

    @staticmethod
    def get():
        """
        Get the list of opened ports by sshd or ssh programs

        :return:    The filtered and splitted output of the lsof command
        :rtype:     list[list[str]]
        """
        if LsofCache._cache is None:
            out = check_run_cmd("lsof", "-i", "TCP", "-P", "-n")
            LsofCache._cache = []
            header_line = True
            for line in out.splitlines():
                if header_line:
                    header_line = False
                    continue
                fields = line.split()
                if fields[0] not in ("ssh", "sshd") and fields[2] != "ssh-tunnel":
                    continue
                LsofCache._cache.append(fields)
        return LsofCache._cache


class PsCache(object):
    """
    Global cache to list autossh running process
    """
    _cache = None

    @staticmethod
    def get():
        """
        Get the list of running autossh process command lines

        :return:    The list of command lines
        :rtype:     list[str]
        """
        if PsCache._cache is None:
            out = check_run_cmd("ps", "aux")
            PsCache._cache = []
            header_line = True
            for line in out.splitlines():
                if header_line:
                    header_line = False
                    continue
                fields = line.split(None, 10)
                if "autossh" not in fields[10].split(None, 2)[0]:
                    continue
                PsCache._cache.append(fields[10])
        return PsCache._cache


class SystemDCache(object):
    """
    Global cache to list SystemD units named ssh tunnel
    """
    _cache = None

    @staticmethod
    def get():
        """
        Get the list of systemd units

        :return:    The filtered and splitted output of the lsof command
        :rtype:     list[str]
        """
        if SystemDCache._cache is None:
            SystemDCache._cache = []
            out = check_run_cmd("systemctl", "list-units", "-q", "--full", "--type=service", "--system",
                                "--no-pager", "--no-legend", "--no-block")
            for line in out.splitlines():
                fields = line.split(None, 5)
                if "ssh" not in fields[0] or "tunnel" not in fields[0]:
                    continue
                SystemDCache._cache.append(fields[0])
            out = check_run_cmd("systemctl", "list-unit-files", "-q", "--full", "--type=service", "--system",
                                "--no-pager", "--no-legend", "--no-block")
            for line in out.splitlines():
                fields = line.split(None, 5)
                if "ssh" not in fields[0] or "tunnel" not in fields[0]:
                    continue
                SystemDCache._cache.append(fields[0])
        return SystemDCache._cache


# Action functions
# ----------------------------------------------------------------------------

class Tunnel(object):
    def __init__(self, config_info):
        super(Tunnel, self).__init__()
        self._name = config_info['tunnel_name']
        self._group_name = config_info["group_name"]
        self._ssh_options = config_info["ssh_options"]
        self._ssh_key = config_info["ssh_key"]
        self._ssh_user = config_info["ssh_user"]
        self._ssh_port = config_info["ssh_port"]
        self._remote_server = config_info["remote_server"]
        self._remote_address = config_info["remote_address"]
        self._remote_port = config_info["remote_port"]
        self._local_address = config_info["local_address"]
        self._local_port = config_info["local_port"]
        self._reverse = config_info["reverse"]

    @property
    def name(self):
        """ :rtype:     str """
        return self._name

    @property
    def group_name(self):
        """ :rtype:     str """
        return self._group_name

    @property
    def ssh_options(self):
        """ :rtype:     list[str] """
        return self._ssh_options

    @property
    def ssh_key(self):
        """ :rtype:     str|None """
        return self._ssh_key

    @property
    def ssh_user(self):
        """ :rtype:     str|None """
        return self._ssh_user

    @property
    def ssh_port(self):
        """ :rtype:     int """
        return self._ssh_port

    @property
    def remote_server(self):
        """ :rtype:     str """
        return self._remote_server

    @property
    def remote_address(self):
        """ :rtype:     str """
        return self._remote_address

    @property
    def remote_port(self):
        """ :rtype:     int """
        return self._remote_port

    @property
    def local_address(self):
        """ :rtype:     str """
        return self._local_address

    @property
    def local_port(self):
        """ :rtype:     int """
        return self._local_port

    @property
    def is_reverse(self):
        """ :rtype:     bool """
        return self._reverse

    def generate_autossh_args(self):
        """
        Generate the arguments required to launch autossh command

        :return:            The arguments for autossh (not shell escaped)
        :rtype:             list[str]
        """
        cmd = ["-M", "0", "-p", to_str(self.ssh_port), "-T", "-N"]
        cmd.extend(self.ssh_options)
        if self.ssh_key is not None:
            cmd.extend(['-i', self.ssh_key])
        user = self.ssh_user if self.ssh_user is not None else getpass.getuser()
        cmd.extend(['-l', user, user + "@" + self.remote_server])
        if self.is_reverse:
            cmd.extend(["-R", self.remote_server + ":" + to_str(self.remote_port) + ":" +
                        self.local_address + ":" + to_str(self.local_port)])
        else:
            cmd.extend(["-L", self.local_address + ":" + to_str(self.local_port) + ":" +
                        self.remote_server + ":" + to_str(self.remote_port)])
        return cmd

    def get_systemd_unit(self):
        """
        Get the details of a the systemd unit corresponding to this tunnel

        :return:            The unit details if found, None otherwise
        :rtype:             str|None
        """
        exitcode, out, err = run_cmd("pidof", "systemd")
        if exitcode != 0:
            return None
        for installed_service in SystemDCache.get():
            if installed_service.endswith("@" + self.remote_server + ".service"):
                return installed_service
            if installed_service.endswith("@" + self.name + ".service"):
                return installed_service
            if installed_service.endswith("@" + self.group_name + ".service"):
                return installed_service
        return None

    def is_running(self):
        """
        Check if this tunnel autossh process is currently running

        :return:            True if it is running, false otherwise
        :rtype:             bool
        """
        cmd_args = self.generate_autossh_args()
        for running_proc_cmd in PsCache.get():
            found = True
            for arg in cmd_args:
                if arg not in running_proc_cmd:
                    found = False
                    break
            if found is True:
                return True
        return False

    def is_unit_installed(self):
        """
        Check if this tunnel has a corresponding systemd unit

        :return:            True if the tunnel's systemd unit is installed, false otherwise
        :rtype:             bool
        """
        if self.get_systemd_unit() is not None:
            return True
        return "sshtunnel@.service" in SystemDCache.get()

    def is_unit_enabled(self):
        """
        Check if the corresponding systemd unit is enabled

        :return:            True if the tunnel has a unit and is installed, False otherwise
        :rtype:             bool
        """
        systemd_unit = self.get_systemd_unit()
        if systemd_unit is None:
            return False
        exitcode, out, err = run_cmd("systemctl", "is-enabled",  systemd_unit)
        return exitcode == 0

    def __hash__(self):
        return hash((self._remote_address, self._remote_port))

    def __eq__(self, other):
        return (self._remote_address, self._remote_port) == (other.remote_adress, other.remote_port)

    def __ne__(self, other):
        return not self.__eq__(other)


def show_status(conf, tunnel_identifiers):
    """
    Render what we known (config, status) of the given servers tunnels

    :param conf:                    The script configuration
    :type conf:                     TunnelConfig
    :param tunnel_identifiers:      The servers we are interested in
    :type tunnel_identifiers:       list[str]|None
    """
    if tunnel_identifiers is None:
        selected_tunnels = conf.all_tunnels
    else:
        selected_tunnels = conf.get_tunnels(tunnel_identifiers)

    tunnel_descriptions = {}
    for tunnel in selected_tunnels:
        tunnel_display = tunnel.name
        if tunnel.is_running():
            tunnel_display += " ["+TermColor.color("running", TermColor.OK)+"]"
        else:
            tunnel_display += " ["+TermColor.color("NOT RUNNING", TermColor.FAIL)+"]"
        if not tunnel.is_unit_installed():
            tunnel_display += " ["+TermColor.color("NOT INSTALLED", TermColor.WARNING)+"]"
        elif tunnel.is_unit_enabled():
            tunnel_display += " ["+TermColor.color("enabled", TermColor.OK)+"]"
        else:
            tunnel_display += " ["+TermColor.color("DISABLED", TermColor.WARNING)+"]"
        tunnel_display += ": "
        tunnel_display += tunnel.local_address + ":" + to_str(tunnel.local_port)
        tunnel_display += " <== " if tunnel.is_reverse else " ==> "
        tunnel_display += tunnel.remote_server + ":" + to_str(tunnel.remote_port) + os.linesep
        tunnel_descriptions[tunnel] = tunnel_display

    tunnels_by_server = index_by(selected_tunnels, lambda t: t.remote_server)
    for server, tunnels in tunnels_by_server.items():
        tunnels_by_group_name = index_by(tunnels, lambda t: t.group_name)
        if len(tunnels_by_group_name.keys()) == 1:
            server_display = server + " (" + first(tunnels_by_group_name)[0] + "):" + os.linesep
            for tunnel in tunnels:
                server_display += indent(tunnel_descriptions[tunnel]) + os.linesep + os.linesep
        else:
            server_display = server + ":" + os.linesep
            for group_name, group_tunnels in tunnels_by_group_name.items():
                server_display += indent() + group_name + ":" + os.linesep
                for tunnel in tunnels:
                    server_display += indent(indent(tunnel_descriptions[tunnel])) + os.linesep + os.linesep
        log.info(server_display)


def show_detected_remote(conf):
    """
    Try to detect other ssh tunnels which are not related to the given configuration,
    and possibly are configured on the remote servers

    FIXME: Improve this. This is just a test for now

    :param conf:                    The script configuration
    :type conf:                     TunnelConfig
    """
    try:
        line = LsofCache.get()
    except StandardError:  # User is not root, so lsof can't run, and we skip detection
        return

    detected_ports = set([])
    if conf:
        for tunnel in conf.all_tunnels:
            detected_ports.add(to_str(tunnel.local_port))

    output = "Detected remote tunnels from other computers:" + os.linesep
    found = False
    for field in line:
        if field != "sshd" or field[9] != "(LISTEN)":
            continue
        listen_ip, details = field[8].split(":", 2)
        if listen_ip != "127.0.0.1" or not re.match(r"^[0-9]+$", details):
            continue
        if details not in detected_ports:
            found = True
            output += indent(details) + os.linesep
    if not found:
        output += indent("Nothing found")
    log.info(output)


def show_config(conf, tunnel_identifiers):
    """
    Show what the parsed config looks like

    :param conf:                    The script configuration
    :type conf:                     TunnelConfig
    :param tunnel_identifiers:      The servers we are interested in
    :type tunnel_identifiers:       list[str]|None
    """
    if tunnel_identifiers is None:
        selected_tunnels = conf.all_tunnels
    else:
        selected_tunnels = conf.get_tunnels(tunnel_identifiers)

    tunnel_descriptions = {}
    for tunnel in selected_tunnels:
        tunnel_info = "name: " + tunnel.name + os.linesep
        tunnel_info += "group name: " + tunnel.group_name + os.linesep
        tunnel_info += "local address: " + tunnel.local_address + os.linesep
        tunnel_info += "local port: " + to_str(tunnel.local_port) + os.linesep
        tunnel_info += "remote server: " + tunnel.remote_server + os.linesep
        tunnel_info += "remote address: " + tunnel.remote_address + os.linesep
        tunnel_info += "remote port: " + to_str(tunnel.remote_port) + os.linesep
        tunnel_info += "reverse: " + ("True" if tunnel.is_reverse else "False") + os.linesep
        tunnel_info += "ssh user: "
        if tunnel.ssh_user is None:
            tunnel_info += "[AUTO]" + os.linesep
        else:
            tunnel_info += tunnel.ssh_user + os.linesep
        tunnel_info += "ssh key: "
        if tunnel.ssh_key is None:
            tunnel_info += "[AUTO]" + os.linesep
        else:
            tunnel_info += tunnel.ssh_key + os.linesep
        tunnel_info += "ssh port: " + to_str(tunnel.ssh_port) + os.linesep
        tunnel_info += "ssh options: " + " ".join([shell_quote(arg) for arg in tunnel.ssh_options]) + os.linesep
        tunnel_descriptions[tunnel] = tunnel_info

    tunnels_by_server = index_by(selected_tunnels, lambda t: t.remote_server)
    for server, tunnels in tunnels_by_server.items():
        tunnels_by_group_name = index_by(tunnels, lambda t: t.group_name)
        if len(tunnels_by_group_name.keys()) == 1:
            server_display = server + " (" + first(tunnels_by_group_name)[0] + "):" + os.linesep
            for tunnel in tunnels:
                server_display += indent() + tunnel.name + ":" + os.linesep
                server_display += indent(indent(tunnel_descriptions[tunnel])) + os.linesep + os.linesep
        else:
            server_display = server + ":" + os.linesep
            for group_name, group_tunnels in tunnels_by_group_name.items():
                for tunnel in tunnels:
                    server_display += indent() + indent() + group_name + ":" + os.linesep
                    server_display += indent(indent(indent(tunnel_descriptions[tunnel]))) + os.linesep + os.linesep
        log.info(server_display)


def check_ssh(conf, tunnel_identifiers):
    """
    Check if the ssh connection works correctly

    :param conf:                    The tunnels configuration
    :type conf:                     TunnelConfig
    :param tunnel_identifiers:      List of tunnel names we want to check. Optional default None
    :type tunnel_identifiers:       list[str]|None
    """
    if tunnel_identifiers is None:
        selected_tunnels = conf.all_tunnels
    else:
        selected_tunnels = conf.get_tunnels(tunnel_identifiers)

    for tunnel in selected_tunnels:
        cmd = ["ssh", "-p", to_str(tunnel.ssh_port)]
        cmd.extend(tunnel.ssh_options)
        if tunnel.ssh_key is not None:
            cmd.extend(['-i', tunnel.ssh_key])
        user = tunnel.ssh_user if tunnel.ssh_user is not None else getpass.getuser()
        cmd.extend([user + "@" + tunnel.remote_server])
        cmd.extend("echo ping_test")
        if tunnel.is_unit_installed():
            exit_code, out, err = run_cmd("sudo", "su", "-l", "ssh-tunnel", "-s", "/bin/bash", "/bin/bash", "-c",
                                          " ".join([shell_quote(arg) for arg in cmd]))
        else:
            exit_code, out, err = run_cmd(*cmd)

        if exit_code != 0 or out.strip() != "ping_test":
            if err is not None:
                err = err.strip()
            if not err:
                err = "Bad response: "+to_str(out).strip()
            log.info(tunnel.remote_server + "/" + tunnel.name + ": " + TermColor.color("Error", TermColor.FAIL) +
                     ": Unable to connect: " + os.linesep + indent(err))
        else:
            log.info(tunnel.remote_server + "/" + tunnel.name + ": " + TermColor.color("Ok", TermColor.OK))


def run(conf, tunnel_identifiers):
    """
    Launch the autossh commands for given servers
    This function doesn't stop unless a tunnel dies or a signal is received.
    In both case it will stop (or kill) the other tunnels and then exit

    :param conf:                    The script configuration
    :type conf:                     TunnelConfig
    :param tunnel_identifiers:      The servers we want to launch the tunnels to
    :type tunnel_identifiers:       list[str]
    """
    if not tunnel_identifiers:
        selected_tunnels = conf.all_tunnels
    else:
        selected_tunnels = conf.get_tunnels(tunnel_identifiers)
    server_list = unique([t.remote_server for t in selected_tunnels])
    for server in server_list:
        # Ensure the server auth is registered
        os.system("ssh-keygen -F '" + server + "' > /dev/null 2>&1 || " +
                  "ssh-keyscan -H '" + server + "' >> ~/.ssh/known_hosts 2>/dev/null")
    out_pipe = None
    err_pipe = None
    autossh_path = which("autossh")
    proc_dict = {}
    try:
        out_pipe = LogPipe(logging.INFO, log)
        err_pipe = LogPipe(logging.WARNING, log)

        # Generate the new autossh proc
        for tunnel in selected_tunnels:
            cmd = [autossh_path]
            cmd.extend(tunnel.generate_autossh_args())
            proc = subprocess.Popen(cmd, stdout=out_pipe, stderr=err_pipe)
            proc_dict[proc.pid] = proc

        # Main loop
        while True:
            for pid, proc in proc_dict.items():
                return_code = wait_proc(proc, timeout=0.1)
                if return_code is None:
                    continue
                else:
                    del proc_dict[pid]
                    raise RuntimeError("autossh stopped with exit code "+to_str(return_code))
    finally:  # Ensure clean process end
        for pid, proc in proc_dict.items():
            try:
                proc.send_signal(signal.SIGTERM)
            except StandardError:
                pass
        timeout = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
        while timeout > datetime.datetime.utcnow() and proc_dict:
            for pid, proc in proc_dict.items():
                if wait_proc(proc, timeout=0.1) is not None:
                    del proc_dict[pid]
                    break
        for pid, proc in proc_dict.items():
            try:
                os.kill(pid, signal.SIGKILL)
            except StandardError:
                pass
        if err_pipe is not None:
            err_pipe.close()
        if out_pipe is not None:
            out_pipe.close()


# Main function
# ----------------------------------------------------------------------------

def main():
    """
    Show information or lauch some ssh tunnels
    FIXME: The script arguments are no so intuitive

    :return:	0 if the software succeeded, a positive integer otherwise
    :rtype:		int
    """
    KillEventHandler.initialise()
    default_config = "sshtunnel.conf"

    usage_str = '''Usage: python sshtunnel.py <command> [<args>]

    Allowed commands:
        status                  Show status of configured tunnels
        config                  Show the loaded configuration details 
        check                   Check the configured tunnels can establish connections
        run                     Start some or all ssh tunnels
    '''

    parser = argparse.ArgumentParser(usage=usage_str)
    parser.add_argument('command', help=argparse.SUPPRESS)
    if len(sys.argv) == 1:
        sys.argv = [sys.argv[0], "status"]

    args = parser.parse_args(sys.argv[1:2])

    if not args.command:
        sys.stderr.write('Unrecognized command' + os.linesep)
        sys.stderr.flush()
        parser.print_help()
        return 1

    if args.command == "status":
        usage_str = '''Usage: python sshtunnel.py status [-h] [--config CONFIG] [--log LOG] [TUNNEL [TUNNEL ...]]'''
        parser = argparse.ArgumentParser(description='SSh tunnelling remote servers: show tunnels status',
                                         usage=usage_str)
        parser.add_argument('--config', '-c', default=None, help="Specify a config file. Default: " + default_config)
        parser.add_argument('--log', '-l', help="Specify a log file. " +
                            "You can specify 'stdout', 'stderr', 'syslog' or a file path. Default: stderr")
        parser.add_argument('TUNNEL', nargs='*', help="The tunnels to starts. It can be a server name, " +
                                                      "a group name or a tunnel name")
        args = parser.parse_args(sys.argv[2:])
        if args.log not in (None, "stdout", "stderr"):
            TermColor.disable()
        init_log(args.log)
        config_file = args.config if args.config else default_config
        if not os.path.isabs(config_file) and not os.path.exists(config_file):
            config_file = os.path.join(script_path, config_file)
        try:
            if os.path.exists(config_file):
                conf = TunnelConfig(config_file)
            elif not args.config:
                log.warning("No config file specified")
                conf = None
            else:
                log.error("Unable to locate config file " + config_file)
                return 1

            tunnels = args.selected_tunnels if len(args.TUNNEL) > 0 else None
            if conf:
                show_status(conf, tunnels)
            if tunnels is None:
                show_detected_remote(conf)
        except KeyboardInterrupt:
            log.warning("Aborted.")
            return 0
        except ConfigError as e:
            log.error("Configuration file " + os.path.abspath(config_file) + " is invalid:" + os.linesep + to_str(e))
            return 1
        except StandardError as e:
            log.error(to_str(e))
            return 1
        return 0

    elif args.command == "config":
        usage_str = '''Usage: python sshtunnel.py config [-h] [--config CONFIG] [--log LOG] [TUNNEL [TUNNEL ...]]'''
        parser = argparse.ArgumentParser(description='SSh tunnelling remote servers: show tunnels configuration',
                                         usage=usage_str)
        parser.add_argument('--config', '-c', default=None, help="Specify a config file. Default: " + default_config)
        parser.add_argument('--log', '-l', help="Specify a log file. " +
                            "You can specify 'stdout', 'stderr', 'syslog' or a file path. Default: stderr")
        parser.add_argument('TUNNEL', nargs='*', help="The tunnels to starts. It can be a server name, " +
                                                      "a group name or a tunnel name")
        args = parser.parse_args(sys.argv[2:])
        if args.log not in (None, "stdout", "stderr"):
            TermColor.disable()
        init_log(args.log)
        config_file = args.config if args.config else default_config
        if not os.path.isabs(config_file) and not os.path.exists(config_file):
            config_file = os.path.join(script_path, config_file)
        try:
            if os.path.exists(config_file):
                conf = TunnelConfig(config_file)
            else:
                log.error("Unable to locate config file " + config_file)
                return 1

            tunnels = args.TUNNEL if len(args.TUNNEL) > 0 else None
            show_config(conf, tunnels)
        except KeyboardInterrupt:
            log.warning("Aborted.")
            return 0
        except ConfigError as e:
            log.error("Configuration file " + os.path.abspath(config_file) + " is invalid:" + os.linesep + to_str(e))
            return 1
        except StandardError as e:
            log.error(to_str(e))
            return 1
        return 0
    elif args.command == "check":
        usage_str = '''Usage: python sshtunnel.py check [-h] [--config CONFIG] [--log LOG] [TUNNEL [TUNNEL ...]]'''
        parser = argparse.ArgumentParser(description='SSh tunnelling remote servers: Check ssh connection',
                                         usage=usage_str)
        parser.add_argument('--config', '-c', default=None, help="Specify a config file. Default: " + default_config)
        parser.add_argument('--log', '-l', help="Specify a log file. " +
                            "You can specify 'stdout', 'stderr', 'syslog' or a file path. Default: stderr")
        parser.add_argument('TUNNEL', nargs='*', help="The tunnels to starts. It can be a server name, " +
                                                      "a group name or a tunnel name")
        args = parser.parse_args(sys.argv[2:])
        if args.log not in (None, "stdout", "stderr"):
            TermColor.disable()
        init_log(args.log)
        config_file = args.config if args.config else default_config
        if not os.path.isabs(config_file) and not os.path.exists(config_file):
            config_file = os.path.join(script_path, config_file)
        try:
            if os.path.exists(config_file):
                conf = TunnelConfig(config_file)
            else:
                log.error("Unable to locate config file " + config_file)
                return 1

            tunnels = args.TUNNEL if len(args.TUNNEL) > 0 else None
            check_ssh(conf, tunnels)
        except KeyboardInterrupt:
            log.warning("Aborted.")
            return 0
        except ConfigError as e:
            log.error("Configuration file " + os.path.abspath(config_file) + " is invalid:" + os.linesep + to_str(e))
            return 1
        except StandardError as e:
            log.error(to_str(e))
            return 1
        return 0

    elif args.command == "run":
        usage_str = 'Usage: python sshtunnel.py run [-h] [--config CONFIG] [--log LOG] [--all | TUNNEL [TUNNEL ...]]'
        parser = argparse.ArgumentParser(description='SSh tunnelling remote servers: start some tunnels',
                                         usage=usage_str)
        parser.add_argument('--config', '-c', default=None, help="Specify a config file. Default: " + default_config)
        parser.add_argument('--log', '-l', help="Specify a log file. " +
                            "You can specify 'stdout', 'stderr', 'syslog' or a file path. Default: stderr")
        parser.add_argument('--all', '-a', action="store_true", help="Start all configured tunnels")
        parser.add_argument('TUNNEL', nargs='*', help="The tunnels to starts. It can be a server name, " +
                                                      "a group name or a tunnel name")
        args = parser.parse_args(sys.argv[2:])
        if args.log not in (None, "stdout", "stderr"):
            TermColor.disable()
        init_log(args.log)
        config_file = args.config if args.config else default_config
        if not os.path.isabs(config_file) and not os.path.exists(config_file):
            config_file = os.path.join(script_path, config_file)
        try:
            if os.path.exists(config_file):
                conf = TunnelConfig(config_file)
            else:
                log.error("Unable to locate config file " + config_file)
                return 1

            if len(args.TUNNEL) > 0:
                if args.all:
                    log.error("You should specify tunnels or --all, not both")
                    return 1
                tunnels = args.TUNNEL
            else:
                if not args.all:
                    log.error("No tunnel specified")
                    return 1
                tunnels = []
                if not tunnels:
                    log.error("No tunnel configured")
                    return 1
            run(conf, tunnels)
        except KeyboardInterrupt:
            log.warning("Aborted.")
            return 0
        except ConfigError as e:
            log.error("Configuration file " + os.path.abspath(config_file) + " is invalid:" + os.linesep + to_str(e))
            return 1
        except StandardError as e:
            log.error(to_str(e))
            return 1
        return 0
    else:
        sys.stderr.write('Unrecognized command ' + to_str(sys.argv[1]) + os.linesep)
        sys.stderr.flush()
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
