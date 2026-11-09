#!/usr/bin/python

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

import socket
import socketserver
socketserver.TCPServer.allow_reuse_address = True
import struct
import sys
import _thread

node_id = 1

from .messages import *

from .options import getOptions
from .tscontainer import TupleSpaceContainer
from .tuplespace import TupleSpace
from .connections import neighbours, connections, sendMessageToNode, connectTo, broadcast_message, broadcast_firstreplyonly, Connection, getMsgId
from . import stats

from . import kernel

from . import utils as utils

process_id = utils.Counter()
ts_ids = utils.Counter()

processes = {}
threads = {}

pthreads = {}
pthread_count = {}

local_ts = TupleSpaceContainer()
blocked_processes = {}

class LindaConnection(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.setblocking(1)

        self.messages = {
            register_process: self.register_process,
            register_thread: self.register_thread,
            unregister_thread: self.unregister_thread,
            unregister_process: self.unregister_process,
            my_name_is: self.my_name_is,
            create_tuplespace: self.create_tuplespace,
            get_connect_details: self.get_connect_details,
            get_new_node_id: self.get_new_node_id,
            get_node_id: self.get_node_id,
            read_tuple: self.read_tuple,
            in_tuple: self.in_tuple,
            out_tuple: self.out_tuple,
            unblock: self.unblock,
            return_tuple: self.return_tuple,
            collect: self.collect,
            copy_collect: self.copy_collect,
            multiple_in: self.multiple_in,
            increment_ref: self.increment_ref,
            decrement_ref: self.decrement_ref,
            get_references: self.get_references,
            get_neighbours: self.get_neighbours,
            get_blocked_list: self.get_blocked_list,
            get_threads: self.get_threads,
            kill_server: self.kill_server,
            }

        # check that the connection comes from an allowed source
        if not isinstance(self.request, Connection) and self.server.allowed_peers:
            ok = False
            for addr in self.server.allowed_peers:
                if self.verify_address(addr):
                    ok = True
                    break
            if not ok:
                print("DENIED ACCESS FROM", self.client_address)
                self.request.shutdown(1)
                self.request.close()
                return

        self.other_pid = None
        self.other_tid = None
        self.other_nid = None
        self.semaphore = threading.Semaphore()

        if not isinstance(self.request, Connection):
            # Here we decide if we can use a better form of communication
            while True:
                msgid, message = utils.recv(self.request)
                m = utils.decode(message)
                if m[0] == begin_session:
                    utils.send(self.request, None, msgid, done)
                    break

                else:
                    print("Unknown Session Setup Message: %s" % (m[0], ))
                    utils.send(self.request, None, msgid, dont_know)

        connections[_thread.get_ident()] = self.request

        while True:
            self.semaphore.release()
            try:
                r = utils.recv(self.request)
                if r is None:
                    break
                msgid, message = r
            except socket.error as msg:
                # should we do something other than silently pass this error?
                message = ""
            self.semaphore.acquire()

            # when a connection is broken a zero length string is returned from self.request.recv
            if not message:
                break

            try:
                m = utils.decode(message)
            except:
                print(repr(message))
                raise

            if m[0] == close_connection:
                 utils.send(self.request, None, msgid, ok)
                 self.request.close()
                 break

            #if not isinstance(self.request, Connection):
            self.handle_msg(msgid, m[0], m[1:])
            #else:
            #    threading.Thread(target=self.handle_msg,args=(msgid, m[0], m[1:])).start()

            del m

        print("closing connection", self.other_tid or self.other_nid)
        del connections[_thread.get_ident()]

        self.request.close()

        # Once a connection is broken we end up here
        #if self.other_pid is not None:
        #    # When a process disconnects ensure that all their references are removed
        #    removeProcess(self.other_pid)
        #    if self.other_pid != kernel.process_id: # don't count the loopback
        #        stats.userDisconnect() # update stats
        if self.other_tid is not None:
            stats.dec_stat("process_con_current")
            try:
                tlist = pthreads[utils.getProcessIdFromThreadId(self.other_tid)]
                del tlist[tlist.index(self.other_tid)]
                del threads[self.other_tid]
            except ValueError:
                pass
        if self.other_nid is not None:
            stats.dec_stat("server_con_current")

    def verify_address(self, addr):
        flds = addr.split("/")
        addr = flds[0]
        if len(flds) == 1:
            mask = 32
        elif len(flds) == 2:
            mask = int(flds[1])

        naddr = struct.unpack("!i", socket.inet_aton(addr))[0] & utils.mask(mask)
        client = struct.unpack("!i", socket.inet_aton(socket.gethostbyname(self.client_address[0])))[0] & utils.mask(mask)
        return naddr == client

    def handle_msg(self, msgid, message, data):
        try:
            self.messages[message](msgid, message, data)
        except KeyError:
            print("Unknown Message: %s (%s)" % (message, str(data)))
            if msgid is None: # if this has a msgid it may have been forwarded by the other node
                node = self.other_nid
            else:
                node = msgid[0]
            utils.send(self.request, node, msgid, done)

    def get_new_node_id(self, msgid, message, data):
        # when a server connects to the network they want a new node id
        if msgid is None:
            node_ids = broadcast_message(get_node_id, data[0])
        else:
#            node_ids = broadcast_message(node, msgid, get_node_id, data[0])
            raise SystemError

        new_id = max(list(map(int, node_ids + [node_id])))+1
        utils.send(self.request, new_id, msgid, str(new_id))

        # the connecting computer has now got an id, add them to our neighbours
        utils.send(self.request, None, msgid, utils.encode((begin_session, )))
        r = utils.recv(self.request)

        utils.sendrecv(self.request, new_id, None, utils.encode((my_name_is, node_id)))

        self.request = Connection(self.request)
        neighbours[new_id] = self.request

        stats.inc_stat("server_con_current")
        stats.inc_stat("server_con_total")

        self.other_nid = new_id

    def get_node_id(self, msgid, message, data):
        utils.send(self.request, None, msgid, str(node_id))

    def my_name_is(self, msgid, message, data):
        # when someone connects who already has an id they need to let us know who they are...
        if utils.isNodeId(data[0]):
            self.other_nid = data[0]
            utils.send(self.request, self.other_nid, msgid, done)
            if data[0] != node_id: # check this isn't the loop back connection
                self.request = Connection(self.request)
            neighbours[int(data[0])] = self.request

            stats.inc_stat("server_con_current")
            stats.inc_stat("server_con_total")

        elif utils.isProcessId(data[0]):
            self.other_pid = data[0]
            stats.userConnect() # update stats
            utils.send(self.request, None, msgid, done)
        else:
            self.other_tid = data[0]
            stats.userConnect() # update stats
            utils.send(self.request, None, msgid, done)

            stats.inc_stat("process_con_current")
            stats.inc_stat("process_con_total")

    def register_process(self, msgid, message, data):
        # When a new process connects they need to acquire new process id
        p_id = "%i!%i" % (node_id, next(process_id))
        processes[p_id] = self.request
        self.other_pid = p_id

        pthreads[p_id] = []
        pthread_count[p_id] = utils.Counter()

        utils.send(self.request, None, msgid, p_id)

    def register_thread(self, msgid, message, data):
        # When a new thread connects they need to acquire new thread id
        p_id = data[0]
        t_id = "%s!%i" % (p_id, next(pthread_count[p_id]))
        pthreads[p_id].append(t_id)
        threads[t_id] = self.request
        self.other_tid = t_id

        utils.send(self.request, None, msgid, t_id)

        stats.inc_stat("process_con_current")
        stats.inc_stat("process_con_total")

    def unregister_thread(self, msgid, message, data):
        # if a process is about to disconnect they can let us know first
        # removeProcess removes any references held by the process
        p_id = utils.getProcessIdFromThreadId(self.other_tid)
        del pthreads[p_id][pthreads[p_id].index(self.other_tid)]
        del threads[self.other_tid]

        utils.send(self.request, None, msgid, done)

    def unregister_process(self, msgid, message, data):
        # if a process is about to disconnect they can let us know first
        # removeProcess removes any references held by the process
        removeProcess(data[0], data[1])

        utils.send(self.request, None, msgid, done)

    def get_connect_details(self, msgid, message, data):
        try:
            int(data[0])
        except ValueError:
            print("Error: ", data[0])
            raise
        # try to find out how to connect to a server
        if int(data[0]) == node_id:
            # they're looking for us! Return our details
            utils.send(self.request, None, msgid, ((self.request.getsockname()[0], getOptions().port), None))
        elif int(data[0]) in list(neighbours.keys()):
            # they're looking for our neighbour, ask them how to connect to them
            r = sendMessageToNode(int(data[0]), None, get_connect_details, int(data[0]))
            if type(neighbours[int(data[0])]) == int: # we don't have a direct connection
                utils.send(self.request, None, msgid, (r[0], neighbours[int(data[0])]))
            else: # we have a direct connection, tell people to go through us
                utils.send(self.request, None, msgid, (r[0], node_id))
        else:
            # we don't know the node they're looking for
            utils.send(self.request, None, msgid, dont_know)

    def create_tuplespace(self, msgid, message, data):
        # return a new tuplespace id
        ts = "%i:%i" % (node_id, next(ts_ids))

        local_ts.newTupleSpace(ts)
        utils.send(self.request, None, msgid, ts)

    def out_tuple(self, msgid, message, data):
        # output a tuple into a tuplespace
        ts, tup = data

        assert utils.isTupleSpaceId(ts)

        if ts in local_ts:
            # we own the given tuplespace - drop the tuple into it
            tup = utils.decode(tup)
            utils.containsTS(tup, lambda t: utils.changeOwner(t, ts))

            local_ts[ts]._out(tup)
            stats.inc_stat("message_out_total")

            utils.send(self.request, None, msgid, done)
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, out_tuple, ts, tup))

    def read_tuple(self, msgid, message, data):
        ts, template, tid, unblockable = data

        if self.other_tid is not None:
            blocked_processes[self.other_tid] = (self.request, self.semaphore)

        assert utils.isTupleSpaceId(ts)

        if ts in local_ts:
            r = local_ts[ts]._rd(tid, template, unblockable)
            stats.inc_stat("message_rd_total")

            if r is not None and self.other_tid is not None:
                del blocked_processes[self.other_tid]
                utils.send(self.request, None, msgid, r)
            elif r is None and self.other_tid is None:
                # if we're talking to another server tell them we're done
                utils.send(self.request, None, msgid, done)
            elif r is not None and self.other_tid is None:
                # if we're talking to another server tell the tuple we've found
                utils.send(self.request, None, msgid, r)
        else:
            def forward_message():
                r = sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, read_tuple, ts, template, tid, unblockable)
                if r != done:
                    utils.send(self.request, None, msgid, r)
            threading.Thread(target=forward_message,args=()).start()

    def in_tuple(self, msgid, message, data):
        ts, template, tid, unblockable = data

        if ts[-1] == "s":
            if int(ts.split(":")[0]) == 0 or int(ts.split(":")[0]) == node_id:
                r = stats._in(template)
                utils.send(self.request, None, msgid, r)
            return

        if self.other_tid is not None:
            blocked_processes[self.other_tid] = (self.request, self.semaphore)

        assert utils.isTupleSpaceId(ts)

        if ts in local_ts:
            r = local_ts[ts]._in(tid, template, unblockable)
            stats.inc_stat("message_in_total")

            if r is not None and self.other_tid is not None:
                del blocked_processes[self.other_tid]
                utils.send(self.request, None, msgid, r)
            elif r is None and self.other_tid is None:
                # if we're talking to another server tell them we're done
                utils.send(self.request, None, msgid, done)
            elif r is not None and self.other_tid is None:
                # if we're talking to another server tell them we're done
                utils.send(self.request, None, msgid, r)
            elif r is None and self.other_tid is not None:
                # we don't have an answer for the process so we finish here and wait for another thread
                # to send the process a return_tuple message
                pass
            else:
                raise SystemError("Error on in_tuple %s" % (str((msgid, message, data)), ))
        else:
            def forward_message():
                r = sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, in_tuple, ts, template, tid, unblockable)
                if r != done:
                    utils.send(self.request, None, msgid, r)
            threading.Thread(target=forward_message,args=()).start()

    def return_tuple(self, msgid, message, data):
        tid, tup = data

        if tid in list(blocked_processes.keys()):
            s, semaphore = blocked_processes[tid]
            del blocked_processes[tid]
            semaphore.acquire()
            utils.send(s, None, None, tup)
            semaphore.release()
            utils.send(self.request, None, msgid, done)
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromThreadId(tid), None, return_tuple, tid, tup))

    def unblock(self, msgid, message, data):
        tid = data[0]

        if tid in list(blocked_processes.keys()):
            s, semaphore = blocked_processes[tid]
            del blocked_processes[tid]
            semaphore.acquire()
            utils.send(s, None, None, unblock)
            semaphore.release()
            utils.send(self.request, None, msgid, done)
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromThreadId(tid), None, unblock, tid))

    def collect(self, msgid, message, data):
        ts, dest_ts, template = data
        if ts in local_ts:
            tups = local_ts[ts].collect(template)
            if tups != []:
                if dest_ts in local_ts:
                    for t in tups:
                        utils.containsTS(t, lambda x: utils.changeOwner(x, dest_ts))
                        local_ts[dest_ts]._out(t)
                else:
                    dest_node = utils.getNodeFromTupleSpaceId(dest_ts)
                    for t in tups:
                        utils.containsTS(t, lambda x: x._addreference(dest_node))
                    sendMessageToNode(dest_node, None, multiple_in, dest_ts, utils.encode(tups))
            utils.send(self.request, None, msgid, str(len(tups)))
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, collect, ts, dest_ts, template))

    def copy_collect(self, msgid, message, data):
        ts, dest_ts, template = data
        if ts in local_ts:
            tups = local_ts[ts].copy_collect(template)
            if tups != []:
                if dest_ts in local_ts:
                    for t in tups:
                        utils.containsTS(t, utils.changeOwner)
                        local_ts[dest_ts]._out(t)

                else:
                    dest_node = utils.getNodeFromTupleSpaceId(dest_ts)
                    for t in tups:
                        utils.containsTS(t, lambda x: x._addreference(dest_node))
                    sendMessageToNode(dest_node, None, multiple_in, dest_ts, utils.encode(tups))

            utils.send(self.request, None, msgid, str(len(tups)))
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, copy_collect, ts, dest_ts, template))

    def multiple_in(self, msgid, message, data):
        ts, tups = data
        if ts in local_ts:
            tups = utils.decode(tups)
            for t in tups:
                utils.containsTS(t, lambda x: utils.changeOwner(x, ts))
                local_ts[ts]._out(t)

                utils.send(self.request, None, msgid, done)
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, multiple_in, ts, tups))

    def increment_ref(self, msgid, message, data):
        ts, ref = data
        if ts in local_ts:
            local_ts.addReference(ts, ref)

            utils.send(self.request, None, msgid, done)
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, increment_ref, ts, ref))

    def decrement_ref(self, msgid, message, data):
        ts, ref = data
        if ts == "0:0": return

        if ts in local_ts:
            ts_obj = local_ts[ts]

            # see the note in the TupleSpace.removeallreference for an explaination of the killlock
            ts_obj.killlock.acquire()

            threading.Thread(target=local_ts.deleteReference,args=(ts, ref)).start()

            utils.send(self.request, None, msgid, done)
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, decrement_ref, ts, ref))

    def get_references(self, msgid, message, data):
        ts = data[0]
        if utils.getNodeFromTupleSpaceId(ts) == node_id:
            if ts in local_ts:
                ts_obj = local_ts[ts]
                ts_obj.ref_semaphore.acquire()
                try:
                    utils.send(self.request, None, msgid, utils.encode(ts_obj.refs))
                finally:
                    ts_obj.ref_semaphore.release()
            else:
                utils.send(self.request, None, msgid, utils.encode([]))
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, get_references, ts))

    def get_blocked_list(self, msgid, message, data):
                ts = data[0]
                if utils.getNodeFromTupleSpaceId(ts) == node_id:
                    if ts in local_ts:
                        ts_obj = local_ts[ts]
                        ts_obj.blocked_semaphore.acquire()
                        try:
                            utils.send(self.request, None, msgid, utils.encode(list(ts_obj.blocked_list.keys())))
                        finally:
                            ts_obj.blocked_semaphore.release()
                    else:
                        utils.send(self.request, None, msgid, utils.encode([]))
                else:
                    utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromTupleSpaceId(ts), None, get_blocked_list, ts))

    def get_threads(self, msgid, message, data):
        pid = data[0]
        if utils.getNodeFromProcessId(pid) == node_id:
            utils.send(self.request, None, msgid, utils.encode(pthreads[pid]))
        else:
            utils.send(self.request, None, msgid, sendMessageToNode(utils.getNodeFromProcessId(pid), None, get_threads, pid))

    def get_neighbours(self, msgid, message, data):
        utils.send(self.request, None, msgid, utils.encode(list(neighbours.keys())))

    def kill_server(self, msgid, message, data):
        if domain_server:
            domain_server.close = True
        server.close = True
        utils.send(self.request, None, msgid, done)

class LindaServer(socketserver.ThreadingTCPServer):
    """\internal
    A simple class the implements a threaded socket server - using the ThreadingTCPServer class provided by Python
    """
    def __init__(self, address, handler, allowed_peers=[]):
        """\internal
        """
        socketserver.ThreadingTCPServer.__init__(self, address, handler)
        self.daemon_threads = True
        self.allowed_peers = allowed_peers
        self.close = False

    def serve_forever(self):
        """Handle one request at a time until doomsday."""
        while not self.close:
            self.handle_request()

    def handle_request(self):
        """Handle one request, possibly blocking."""
        try:
            self.socket.settimeout(1.0)
            request, client_address = self.get_request()
            self.socket.settimeout(None)
        except socket.error:
            return
        if self.verify_request(request, client_address):
            try:
                self.process_request(request, client_address)
            except:
                self.handle_error(request, client_address)
                self.close_request(request)

    def process_request(self, request, client_address):
        """Start a new thread to process the request."""
        import threading
        t = threading.Thread(target = self.process_request_thread,
                             args = (request, client_address))
        if self.daemon_threads:
            t.setDaemon (1)
        t.start()

def removeProcess(pid, local=True):
    """\internal
    \brief Called if a process leaves the system to ensure that no references that the process had remain in the system.

    If a process exits normally then all this should be unnessicary, however we can't trust user processes.
    """
    # check it actually is a process and not another node
    if not utils.isProcessId(pid):
        return

    # check that it wasn't blocked when the connection was lost
    for tid in list(blocked_processes.keys()):
        if utils.getProcessIdFromThreadId(tid) == pid:
            del blocked_processes[tid]

    # remove any references the process may have had to our processes
    for ts in local_ts:
        local_ts.deleteAllReferences(ts, pid)

    # if the process was connected to us then broadcast the fact that it has left the system
    if local:
        broadcast_message(unregister_process, pid, False)

import threading
class KernelImport(threading.Thread):
    """\internal
    We need to create a loopback connection, but we can't do that until the server has started - however we can't 
    do it after the server has been started - so we do it in another thread!
    """
    def run(self):
        kernel.connect(options.port)
        kernel.process_id = node_id
        kernel.use_domain = options.use_domain
        kernel.message(my_name_is, node_id)

domain_server = None
def main(connection_class = LindaConnection):
    """\internal
    \brief Parse command line options and start the server.
    """
    global server, domain_server, node_id, neighbours, local_ts, options

    kernel.run_as_server = True

    options = getOptions()

    if options.peer:
        options.peer.append("127.0.0.1") # always allow local connections.

    def lookupname(addr):
        try:
            addr,r = addr.split("/")
        except ValueError:
            r = "32"

        addr = socket.gethostbyname(addr)
        if addr.count(".") != 3:
            print("%s is not in n.n.n.n[/r] format" % (addr+"/"+r))
            sys.exit(0)
        return addr+"/"+r

    server = LindaServer((options.bindaddress, options.port),
                          connection_class,
                          list(map(lookupname, options.peer)))

    try:
        from . import domain_socket
    except ImportError:
        pass
    else:
        if options.use_domain:
            domain_server = domain_socket.LindaDomainServer("/tmp/pylinda", connection_class, [])
            threading.Thread(target=domain_server.serve_forever, args=()).start()

    if options.connect != "":
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((options.connect, options.connectport))
        except socket.error as e:
            print("Unable to connect to server %s:%i. Reason: %s" % (options.connect, options.connectport, e))
            sys.exit(-1)

        utils.send(s, None, None, utils.encode((begin_session,)))
        r = utils.recv(s)
        if r == (None, ""):
            print("Connection Failed: Probably denied by the other server")
            return

        utils.send(s, None, None, utils.encode((get_node_id, )))
        node = int(utils.recv(s)[1])

        utils.send(s, node, None, utils.encode((get_new_node_id, options.port)))
        node_id = int(utils.recv(s)[1])

        #s = Connection(s)

        server.process_request(s, (options.connect, options.connectport))

        neighbours[node] = s
    else:
        local_ts.newTupleSpace("0:0")

    # import the kernel
    KernelImport().start()

    if not options.daemon:
        from .monitor import monitor
        monitor.start()

    while True:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            if domain_server:
               domain_server.close = True
            if options.daemon:
                raise
            else:
                monitor.keyboard_interrupt = True
                continue
        break
