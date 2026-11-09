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

## \namespace utils
## \brief This module contains all the various functions that are shared amongst the linda modules
##
## \internal

import _thread
import struct
import socket

import pickle
encode = pickle.dumps
decode = pickle.loads

try:
    dontwait_flag = socket.MSG_DONTWAIT
except AttributeError:
    dontwait_flag = 0

#from linda.profile import P

max_msg_size = 1
def recv(s, msgid=None):
    """\internal
    \brief Receive a message from the given socket

    \param s A socket object
    """
    if isinstance(s, connections.Connection):
        return s.recv(msgid)
    msg = ""
    while len(msg) < 4:
        r = s.recv(max_msg_size)
        if r == "":
            return None, ""
        msg += r

    size, msg = struct.unpack("!I", msg[:4])[0], msg[4:]

    if size > len(msg):
        while size > len(msg):
            r = s.recv(size - len(msg))
            if r == "":
                return None, ""
            msg += r

    assert size == len(msg)

    return None, decode(msg[:size])

def send(s, dest_node, msgid, msg):
    """\internal
    \brief Sends a message on the given socket

    \param s A socket object
    """
    if isinstance(s, connections.Connection):
        return s.send(dest_node, msgid, msg)
    msg = encode(msg)
    try:
        s.sendall(struct.pack("!I", len(msg)) + msg, dontwait_flag)
    except socket.error:
        # if we get an error here then just continure, we'll pick it up and exit properly when we next do a recv
        pass

def sendrecv(s, dest_node, msgid, msg):
    return recv(s, send(s, dest_node, msgid, msg))

def containsTS(tup, func):
     """\internal
     \brief Recursively scans the given tuple (tup) for a tuple space and calls func with each tuple space that is found as an argument

     This function is very useful when used in conjuction with map.
     \code
     map(list_of_tuples, lambda x: utils.containsTS(x, func))
     \endcode

     \param tup The tuple to be checked
     \param func The function to be called for each Tuplespace reference that is found
     """
     def myfunc(t):
         if type(t) == tuple:
             containsTS(t, func)
         elif isinstance(t, TupleSpace):
             func(t)
     list(map(myfunc, tup))

def changeOwner(t, to):
    """\internal
    \brief Changes the owner of the given tuplespace reference to the given process/server.

    \param t A tuplespace reference
    \param to A process/server id
    """
    t._addreference(to)
    t._delreference(t.owner)
    t.owner = to

def isTupleSpaceId(id):
    """\internal
    \brief Checks if the given id is a valid tuplespace id

    This function does not check that a tuplespace exists with this id, only the id is of the correct format
    \param id The id to be checked
    """
    try:
        if type(id) != str:
            return False
        node, num = id.split(":")
        int(node)
        int(num)
    except ValueError:
        return False
    else:
        return True

def isNodeId(id):
    """\internal
    \brief Checks if the given id is a valid node id

    This function does not check that a node exists with this id, only the id is of the correct format
    \param id The id to be checked
    """
    return type(id) == int

def isProcessId(id):
    """\internal
    \brief Checks if the given id is a valid process id

    This function does not check that a process exists with this id, only the id is of the correct format
    \param id The id to be checked
    """
    try:
        if type(id) != str:
            return False
        pid, num = id.split("!")
        int(pid)
        int(num)
    except ValueError:
        return False
    else:
        return True

def isThreadId(id):
    """\internal
    \brief Checks if the given id is a valid thread id

    This function does not check that a thread exists with this id, only the id is of the correct format
    \param id The id to be checked
    """
    try:
        if type(id) != str:
            return False
        pid, num, thread = id.split("!")
        int(pid)
        int(num)
        int(thread)
    except ValueError:
        return False
    else:
        return True

def getNodeFromTupleSpaceId(ts):
    """\internal
    \brief Returns the node that owns the given tuplespace

    \param ts The tuplespace whoes owner you want
    \return The node who owns the tuplespace
    """
    assert isTupleSpaceId(ts), "Not a tuplespace id %s" % (ts, )

    if int(ts.split(":")[0]) == 0:
        return 1
    else:
        return int(ts.split(":")[0])

def getNodeFromProcessId(pid):
    """\internal
    \brief Returns the node that owns the given process

    \param ts The process whos owner you want
    \return The node who owns the tuplespace
    """
    assert isProcessId(pid), "Not a process id %s" % (pid, )

    return int(pid.split("!")[0])

def getNodeFromThreadId(ts):
    assert isThreadId(ts), "Not a process id %s" % (ts, )

    return int(ts.split("!")[0])

def getProcessIdFromThreadId(tid):
    assert isThreadId(tid), "Not a process id %s" % (tid, )

    return "!".join(tid.split("!")[:2])

class Counter:
    def __init__(self, start=0):
        self.counter = start
        self.lock = _thread.allocate_lock()
        self.limit = None

    def __call__(self):
        self.lock.acquire()
        try:
            self.counter = self.counter + 1
            if self.limit and self.counter > self.limit:
                raise ValueError("Counter Exceeded Maximum Allowed Value")
            return self.counter
        finally:
            self.lock.release()

    def __next__(self):
        return self()

    def setLimit(self, limit):
        self.limit = limit

def mask(bits):
    assert 0 <= bits <= 32

    return ~((1 << (32 - bits)) - 1)

from linda import connections
