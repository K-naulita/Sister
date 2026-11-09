#    Copyright 2004 Andrew Wilkinson <aw@cs.york.ac.uk>.
#
#    This file is part of PyLinda (http://www-users.cs.york.ac.uk/~aw/pylinda)
#
#    PyLinda is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 2.1 of the License, or
#    (at your option) any later version.
#
#    PyLinda is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with PyLinda; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

## \namespace kernel
## \brief This module provides the client code to allow a program to interface with a linda server.
##
## The key elements are the TupleSpace class and the universe global tuple space.
## \attention This module should not be imported directly, it is imported automatically when the linda package is imported.
## \author Andrew Wilkinson <aw@cs.york.ac.uk>
##

import gc
import socket
import time
import _thread
import threading

from linda.messages import *

run_as_server = False

_connected = False
class NotConnected(Exception):
    """\brief If this exception is raised then you forgot to call the connect method before accessing a linda primitive.
    """
    pass

class TupleSpace:
    """\brief This class represents a tuplespace.
    """
    def __init__(self, tsid=None, gc=True):
        """\brief Constructor for the tuplespace.

        This function contacts the local server and creates a new tuplespace there.
        \param universe Never set this parameter - it is only used internally
        """
        if tsid:
            self._id = tsid
            self.owner = process_id or "0!0"
            self._gc = gc
        else:
            if not _connected:
                raise NotConnected

            self.owner = process_id
            self._id = message(create_tuplespace)
            self._addreference(self.owner)
            self._gc = True

    def __getstate__(self):
        """\internal
        \brief This function is used for pickling the object
        """
        return [self._id]
    def __setstate__(self, state):
        """\internal
        \brief This function is used for pickling the object
        """
        self.owner = process_id
        self._id = state[0]
        self.decref = False
        self._gc = True

    def __del__(self):
        """\brief Tuplespace destructor
        """
        if self._gc:
            self._delreference(self.owner)

    def _addreference(self, ref):
        """\internal
        \brief Adds a new reference to the tuplespace
        """
        message(increment_ref, self._id, ref)

    def _delreference(self, ref):
        """\internal
        \brief Deletes a reference to the tuplespace
        """
        message(decrement_ref, self._id, ref)

    def _out(self, tup):
        """\brief Outputs the given tuple to the tuplespace

        \param tup Sends the given tuple to the tuplespace
        """
        if type(tup) is not tuple:
            raise TypeError("out only takes a tuple, not %s" % (type(tup)))

        utils.containsTS(tup, lambda t: t._addreference(utils.getNodeFromTupleSpaceId(self._id)))

        message(out_tuple, self._id, utils.encode(tup))

    def _rd(self, template):
        """\brief Reads a tuple matching the given template

        \param template The template used to match.
        \return The matching tuple
        """
        if type(template) is not tuple:
            raise TypeError("rd only takes a tuple, not %s" % (type(template)))

        r = message(read_tuple, self._id, template, getThreadId(), False)
        if r != unblock:
            return utils.decode(r)
        else:
            raise SystemError("Non-blocking primitive received an unblock command")

    def _in(self, template):
        """\brief Destructivly reads a tuple matching the given template

        \param template The template used to match.
        \return The matching tuple
        """
        if type(template) is not tuple:
            raise TypeError("in only takes a tuple, not %s" % (type(template)))

        r = message(in_tuple, self._id, template, getThreadId(), False)
        if r != unblock:
            return utils.decode(r)
        else:
            raise SystemError("Non-blocking primitive received an unblock command")

    def _rdp(self, template):
        """\brief Reads a tuple matching the given template.

        This follows the Principled Semantics for inp as described by Jacob and Wood
        \param template The template used to match.
        \return The matching tuple
        """
        if type(template) is not tuple:
            raise TypeError("rdp only takes a tuple, not %s" % (type(template)))

        r = message(read_tuple, self._id, template, getThreadId(), True)
        if r != unblock:
            return utils.decode(r)
        else:
            return None

    def _inp(self, template):
        """\brief Destructivly reads a tuple matching the given template.

        This follows the Principled Semantics for inp as described by Jacob and Wood
        \param template The template used to match.
        \return The matching tuple
        """
        if type(template) is not tuple:
            raise TypeError("inp only takes a tuple, not %s" % (type(template)))

        r = message(in_tuple, self._id, template, getThreadId(), True)
        if r != unblock:
            return utils.decode(r)
        else:
            return None

    def collect(self, ts, template):
        """\brief Destructivly moves all matching tuples from this Tuplespace to the given Tuplespace.

        \param ts The tuplespace to move the tuples into.
        \param template The template used to match.
        \return The number of matched tuples
        """
        if ts.__class__ != TupleSpace:
            raise TypeError("collect only takes a tuplespace, not %s" % (ts.__class__))
        if type(template) is not tuple:
            raise TypeError("collect only takes a tuple, not %s" % (type(template)))

        r = message(collect, self._id, ts._id, template)
        try:
            return int(r)
        except ValueError:
            raise SystemError("Unexpected reply to collect message - %s" % r)

    def copy_collect(self, ts, template):
        """\brief Copies all matching tuples from this Tuplespace to the given Tuplespace.

        \param ts The tuplespace to move the tuples into.
        \param template The template used to match.
        \return The number of matched tuples
        """
        if ts.__class__ != TupleSpace:
            raise TypeError("copy_collect only takes a tuplespace, not %s" % (ts.__class__))
        if type(template) is not tuple:
            raise TypeError("copy_collect only takes a tuple, not %s" % (type(template)))

        r = message(copy_collect, self._id, ts._id, template)
        try:
            return int(r)
        except ValueError:
            raise SystemError("Unexpected reply to collect message - %s" % r)

    def __str__(self):
        """\brief Get a string representation of the tuplespace
        """
        if self._id == "0:0":
            return "<Universal Tuplespace>"
        else:
            return "<TupleSpace %s (%s)>" % (self._id, str(self.owner))
    def __repr__(self):
        """\brief Get a string representation of the tuplespace
        """
        if self._id == "0:0":
            return "<Universal Tuplespace>"
        else:
            return "<TupleSpace %s (%s)>" % (self._id, str(self.owner))

    __safe_for_unpickling__ = True

def getStatsTS():
    return TupleSpace(process_id.split("!")[0] + ":s", False)

# delay importing the utils module until after we've defined TupleSpace as the utils class indirectly requires it
from linda import utils
utils.TupleSpace = TupleSpace

msg_semaphore = threading.Semaphore()
counter = utils.Counter()

def message(*msg):
    """\internal
    \brief Send the given message to the local server
    \param msg The message to send
    """
    if not _connected:
        raise NotConnected

    if run_as_server:
        msg_semaphore.acquire()
    try:
        s = getSocket()
        try:
            utils.send(s, None, None, utils.encode(msg))
        except socket.error as xxx_todo_changeme:
            (n, msg) = xxx_todo_changeme.args
            if msg == "Broken Pipe":
                print("Broken Pipe")
            else:
                raise
        return utils.recv(s)[1]
    finally:
        if run_as_server:
             msg_semaphore.release()

import sys
class _Process:
    """\internal
    \brief Connect to local server
    """
    def __init__(self):
        global s, process_id, _connected


        try:
            from . import domain_socket
        except ImportError:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", port))
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.connect("/tmp/pylinda")
            except socket.error:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("127.0.0.1", port))

        obj = threading.currentThread()
        obj.pylinda_con = None, s

        _connected = True

        message(begin_session)

        if not run_as_server:
            process_id = message(register_process)
            thread_id = message(register_thread, process_id)
            obj.pylinda_con = thread_id, s
        else:
            process_id = None

def getThreadId():
    if run_as_server:
        return "0!0!0"
    obj = threading.currentThread()
    if hasattr(obj, "pylinda_con"):
        return obj.pylinda_con[0]
    else:
        getSocket()
        return getThreadId()

def getSocket():
    if run_as_server:
        return s
    obj = threading.currentThread()
    if hasattr(obj, "pylinda_con"):
        return obj.pylinda_con[1]
    else:
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        soc.connect(("127.0.0.1", port))
        obj.pylinda_con = None, soc
        message(begin_session)
        thread_id = message(register_thread, process_id)
        obj.pylinda_con = thread_id, obj.pylinda_con[1] #thread_connection[thread.get_ident()][1]
        return soc

def connect(cport=2102):
    """\brief Connect to a server running on the local machine.

    This function must be called before any Linda primitives are used otherwise a NotConnected exception will be raised.
    \param cport The port to connect to
    """
    global _process, port
    port = cport
    _process = _Process()

    return True

def disconnect():
    message(unregister_thread)
    obj = threading.currentThread()
    if hasattr(obj, "pylinda_con"):
        obj.pylinda_con[1].close()
        delattr(obj, "pylinda_con")
    #thread_connection[thread.get_ident()][1].close()
    #del thread_connection[thread.get_ident()]

def close():
    thread_connection = {}
    s.close()

_process = None

process_id = None

## \var Tuplespace universe
## A reference to the universal tuplespace
universe = TupleSpace("0:0", False)
uts = universe

# These options control whether we want to use Unix Domain sockets or Shared Memory
use_domain = True
use_shm = True

