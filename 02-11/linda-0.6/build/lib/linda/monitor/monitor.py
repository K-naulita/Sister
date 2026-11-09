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

import threading
try:
    import readline
except ImportError:
    pass
import time
import os.path
import pyggy

from linda import server
from linda import connections

keyboard_interrupt = False

def start():
    t = Thread()
    t.setDaemon(True)
    t.start()

def genlexer():
    return pyggy.getlexer(os.path.dirname(__file__)+os.sep+"pyg_monitor.pyl")
def genparser():
    return pyggy.getparser(os.path.dirname(__file__)+os.sep+"pyg_monitor.pyg")

class Thread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        time.sleep(2) # wait for server to start properly
        while True:
            try:
                self.realrun()
                break
            except:
                print "Caught exception"
                raise

    def realrun(self):
        global keyboard_interrupt

        l,ltab = genlexer()
        p,ptab = genparser()
        p.setlexer(l)

        while True:
            print ">",
            try:
                text = raw_input()
            except KeyboardInterrupt:
                if self.doCommand(("quit", )):
                    break
            except EOFError:
                if self.doCommand(("quit", )):
                    break
            keyboard_interrupt = False
            try:
                l.setinputstr(text)
                command = p.parse()
            except pyggy.ParseError,e:
                print "Syntax Error!"
                print e
                continue
            else:
                if self.doCommand(pyggy.proctree(command, ptab)):
                    break

    def doCommand(self, command):
        global keyboard_interrupt
        if command is None:
            return
        elif command[0] == "quit":
            print "Shutting down..."
            server.domain_server.close = True
            server.server.close = True
            # shut down the kernel's connection to the server
            server.kernel.close()

            for c in server.connections.values():
                c.close()
            return True
        elif command[0] == "list":
            print "TupleSpaces: " + " ".join(server.local_ts.keys())
        elif command[0] == "inspect":
            try:
                ts = server.local_ts[command[1]]
            except KeyError:
                print "No such tuplespace"
                return
            ts.lock.acquire()
            try:
                print "References:", ts.refs
                print "Blocked:", ts.blocked_list
                print "Tuples:"
                for t in ts.ts.matchAllTuples():
                     print str(t)+" ",
            finally:
                ts.lock.release()
            print ""
        elif command[0] == "route":
            ns = connections.neighbours.keys()
            ns.sort()
            for n in ns:
                print "%i -> %s" % (n, connections.neighbours[n])
        elif command[0] == "watch":
            if command[1] is None:
                delay = 10
            else:
                delay = min(0.1, command[1])
            while True:
                self.doCommand(command[2])
                if keyboard_interrupt:
                    keyboard_interrupt = False
                    return        
                time.sleep(delay)
        elif command[0] == "help":
            print "Possible commands..."
            print "list - Print list of all tuplespaces on the server"
            print "inspect <tsid> - List the tuples in the given tuplespace"
            print "watch <delay> <command> - Repeat the given command every <delay> seconds.\n    If left out <delay> defaults to 10."
            print "quit - Shut down the server."
        else:
            print "Unknown command", command
