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

import struct
import _thread
import threading
import socket

from .messages import *

neighbours = {}

connections = {}

msg_header_size = struct.calcsize("!Iiiii")

class Connection:
    def __init__(self, socket):
        def socket_watcher():
            buf = ""
            while True:
                size = 0
                r = ""
                if buf == "":
                    r = self.socket.recv(1024)
                    if r == "":
                        self.close()
                        return
                msg = buf + r
                size = struct.unpack("!I", msg[:4])[0]
                prevlen = len(msg)
                while len(msg) < size:
                    msg += self.socket.recv(size - len(msg))
                    if len(msg) == prevlen:
                        self.close()
                        return
                    prevlen = len(msg)
                size, dest_id, src, dest, msgid = struct.unpack("!Iiiii", msg[:msg_header_size])
                #print "recieved", size, dest_id, src, dest, msgid, repr(msg[msg_header_size:])
                msgid = (src, dest, msgid)
                msg, buf = msg[msg_header_size:size], msg[size:]
                if dest_id != server.node_id:
                    utils.send(getNeighbourDetails(dest_id), dest_id, msgid, decode(msg))
                elif dest == server.node_id:
                    self.store_lock.acquire()
                    try:
                        self.message_store.append((msgid, decode(msg)))
                        #print "%i %i messages stored" % (len(self.message_store), len(self.return_message_store))
                        self.recv_lock.set()
                    finally:
                        self.store_lock.release()
                else:
                    self.store_lock.acquire()
                    try:
                        self.return_message_store[msgid] = decode(msg)
                        if msgid in self.blocked_store:
                            self.blocked_store[msgid].set()
                    finally:
                        self.store_lock.release()

        self.socket = socket
        self.send_lock = threading.Semaphore()
        self.recv_lock = threading.Event()
        self.store_lock = threading.Semaphore()
        self.message_store = [] # this stores messages sent to us
        self.return_message_store = {} # this stores return messages to message we sent
        self.blocked_store = {} # this stores threads waiting for a message
        self.closed = False

        thread = threading.Thread(target=socket_watcher)
        _thread.setDaemon(True)
        _thread.start()

    def send(self, dest_node, msgid, msg):
        if self.closed:
            return None
        assert dest_node is not None or msgid is not None
        if msgid is None:
            msgid = (server.node_id, dest_node, getMsgId())
        elif dest_node is None:
            dest_node = msgid[0] # we have a msgid so we're returning the message to the source
        msg = encode(msg)
        self.send_lock.acquire()
        #print "sending", dest_node, msgid[0], msgid[1], msgid[2], repr(msg)
        try:
            self.socket.sendall(struct.pack("!Iiiii", msg_header_size + len(msg), dest_node, msgid[0], msgid[1], msgid[2]) + msg)
        finally:
            self.send_lock.release()
        return msgid

    def recv(self, msgid):
        if self.closed:
            return None, ""
        if msgid is None:
            while True:
                if self.closed:
                    break
                self.store_lock.acquire()
                try:
                    if len(self.message_store) > 0:
                        r, self.message_store = self.message_store[0], self.message_store[1:]
                        if len(self.message_store) == 0:
                            self.recv_lock.clear()
                        return r
                finally:
                     self.store_lock.release()
                self.recv_lock.wait()
            return None, ""
        else:
            self.store_lock.acquire()
            if msgid in self.return_message_store:
                try:
                    return self.return_message_store[msgid]
                finally:
                    del self.return_message_store[msgid]
                    self.store_lock.release()
            else:
                try:
                     self.blocked_store[msgid] = threading.Event()
                finally:
                     self.store_lock.release()
                self.blocked_store[msgid].wait()
                del self.blocked_store[msgid]
                self.store_lock.acquire()
                try:
                    return self.return_message_store[msgid]
                finally:
                    del self.return_message_store[msgid]
                    self.store_lock.release()

    def setblocking(self, value):
        self.socket.setblocking(value)
    def getsockname(self):
        return self.socket.getsockname()
        
    def shutdown(self, i):
        self.socket.shutdown(i)
    def close(self):
        self.closed = True
        self.socket.close()
        self.recv_lock.set()
        for e in list(self.blocked_store.values()):
            e.set()

def getNeighbourDetails(node):
    if node not in neighbours:
        connectTo(node)
        return getNeighbourDetails(node)
    elif type(neighbours[node]) == int:
        return getNeighbourDetails(neighbours[node])
    else:
        return neighbours[node]

def sendMessageToNode(node, msgid, *args):
    """\internal
    Helper function to ensure that we have connected to the server we want to talk to, and to send the message.
    """
    if node == 0:
        node = 1

    if node == server.node_id:
        return kernel.message(args)

    s = getNeighbourDetails(node)
    return utils.sendrecv(s, node, msgid, utils.encode(args))

connect_lock = threading.Semaphore()
def connectTo(node):
    connect_lock.acquire()
    try:
        if node not in neighbours: # check that we still don't know how to connect
            connectToMain(node)
    finally:
        connect_lock.release()
    
def connectToMain(node):
    """\internal
    \brief Find the address of, and connect to a new server.
    """
    details = broadcast_firstreplyonly(get_connect_details, node)
    neighbours[node] = details[1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(details[0])
    except socket.error as e:
        print("failed to connect to", details)
        neighbours[node] = details[1]
    else:
        if utils.sendrecv(s, node, None, utils.encode((begin_session, )))[1] == "":
            print("failed to connect to", details)
            neighbours[node] = details[1]
            return
        neighbours[node] = s
        
        utils.send(s, None, None, utils.encode((get_node_id, )))
        cnode = int(utils.recv(s)[1])
        
        if cnode != node:
            print("failed to connect to", details)
            neighbours[node] = details[1]
            s.shutdown(1)
            s.close()
            return
        
        msgid = sendMessageToNode(node, None, my_name_is, server.node_id)
        
        s = Connection(s)
        neighbours[node] = s
        addr = s.socket.getsockname()
        addr = (socket.gethostbyname(addr[0]), addr[1])
        server.server.process_request(s, addr)

def broadcast_message(*args):
    memo = [server.node_id]
    r = []
    todo = list(neighbours.keys())

    while len(todo) > 0:
        node, todo = todo[0], todo[1:]
        if node in memo:
            continue
        else:
            memo.append(node)

        m = sendMessageToNode(node, None, *args)

        if m != (None, "") and m != dont_know:
            r.append(m)

        n = sendMessageToNode(node, None, get_neighbours)
        if n == (None, ""):
            print("Broken connection to %i" % (node, ))
        elif n != dont_know:
            todo.extend(utils.decode(n))
    return r

def broadcast_firstreplyonly(*args):
    memo = [server.node_id]
    todo = list(neighbours.keys())
    while len(todo) > 0:
        node, todo = todo[0], todo[1:]
        if node in memo:
            continue
        else:
            memo.append(node)

        m = sendMessageToNode(node, None, *args)

        if m != (None, "") and m != dont_know:
            return m

        n = sendMessageToNode(node, None, get_neighbours)
        if n != (None, "") and n != dont_know:
            todo.extend(utils.decode(n))

    return dont_know

from . import utils
from .utils import encode, decode
getMsgId = utils.Counter()

from . import kernel

from . import server
