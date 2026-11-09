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

## \namespace tuplespace
## \brief This module contains the class the actually implements a tuplespace.
## \internal
##
## \attention If you're not developing the PyLinda server then you actually want the kernel::TupleSpace class.
## \author Andrew Wilkinson <aw@cs.york.ac.uk>
##

import threading

from .tuplecontainer import TupleContainer, doesMatch, NoTuple
from .messages import get_references, decrement_ref, unblock, return_tuple, get_blocked_list, get_threads

from . import kernel

# Nasty hack to make lists work inside our tuplespace
class ImmutableList:
    def __init__(self, l):
        self.l = l
        self.hash = hash(tuple(l))
    def __eq__(self, other):
        return isinstance(other, ImmutableList) and (self.l == other.l)
    def __hash__(self):
        return self.hash

def convertLists(tup):
    def convert(t):
        if t == list:
            return ImmutableList
        elif isinstance(t, list):
            return ImmutableList(t)
        elif isinstance(t, tuple):
            return convertLists(t)
        else:
            return t
    return tuple(map(convert, tup))

def decodeLists(tup):
    def decode(t):
        if t == ImmutableList:
            return list
        elif isinstance(t, ImmutableList):
            return t.l
        elif isinstance(t, tuple):
            return decodeLists(t)
        else:
            return t
    return tuple(map(decode, tup))

## \class TupleSpace
## \internal
## \brief This class is the actual tuplespace stored on the server. The class kernel::TupleSpace is a reference to one instance of this class.
##
## \author Andrew Wilkinson <aw@cs.york.ac.uk>
##
class TupleSpace:
    def __init__(self, _id):
        self._id = _id
        self.lock = threading.Semaphore()

        self.ts = TupleContainer()

        self.killlock = threading.Semaphore()
        self.ref_semaphore = threading.Semaphore()
        self.blocked_semaphore = threading.Semaphore()
        self.refs = []
        self.blocked_list = {}

    def __del__(self):
        print("TupleSpace %s being deleted..." % (self._id, ))

    ## \brief This function is called to put a tuple into the tuplespace
    def _out(self, tup):
        tup = convertLists(tup)

        self.lock.acquire()
        try:
            # Before we add the tuple to the tuplespace we need to check if any processes are waiting on a template
            # that this tuple matches - first we get a list of the blocked processes
            self.blocked_semaphore.acquire()
            try:
                blist = list(self.blocked_list.keys())
            finally:
                self.blocked_semaphore.release()

            def check_blocked(tid):
                # for each blocked process...
                if doesMatch(self.blocked_list[tid][0], tup):
                    # ... if the tuple matches their template wake them up.
                    destructive = self.blocked_list[tid][2]
                    del self.blocked_list[tid]

                    def do_return_tuple():
                        utils.containsTS(tup, lambda x: x._addreference(utils.getProcessIdFromThreadId(tid))) # update references for the tuple
                        kernel.message(return_tuple, tid, utils.encode(tup)) # return the tuple to the process

                    threading.Thread(target=do_return_tuple).start()

                    if destructive == True: # if they were doing an in then stop here, otherwise we continue
                        raise EOFError

            try:
                list(map(check_blocked, blist))
            except EOFError:
                return

            self.ts.add(tup) # add the tuple to the tuplespace
        finally:
            self.lock.release()

    ## \brief This function is called when a process reads from the tuplespace
    ##
    ## If a matching tuple is immediatly found then it is returned, otherwise <b>None</b> is returned and
    ## the process is added to the list of blocked processes
    def _rd(self, tid, pattern, unblockable):
        pattern = convertLists(pattern)

        self.lock.acquire()
        try:
            try:
                # try to match a tuple
                r = self.ts.matchOneTuple(pattern)
            except NoTuple:
                # if we didn't find a tuple then we block
                self.blocked_list[tid] = (pattern, unblockable, False)
                # check that we have created a deadlock
                if self.isDeadLocked():
                    # if we have then unblock a random process
                    self.unblockRandom()
            else:
                # we found a tuple so update the references and return it
                utils.containsTS(r, lambda x: x._addreference(utils.getProcessIdFromThreadId(tid)))
                return utils.encode(decodeLists(r))
        finally:
            self.lock.release()

    ## \brief This function is called when a process ins from the tuplespace
    ##
    ## If a matching tuple is immediatly found then it is returned, otherwise <b>None</b> is returned and
    ## the process is added to the list of blocked processes
    def _in(self, tid, pattern, unblockable):
        pattern = convertLists(pattern)

        self.lock.acquire()
        try:
            try:
                # try to match a tuple
                r = self.ts.matchOneTuple(pattern)
            except NoTuple:
                # if we didn't find a tuple then we block
                self.blocked_list[tid] = (pattern, unblockable, True)
                # check that we have created a deadlock
                if self.isDeadLocked():
                    # if we have then unblock a random process
                    self.unblockRandom()
            else:
                # we found a tuple so update the references and return it
                utils.containsTS(r, lambda x: x._addreference(utils.getProcessIdFromThreadId(tid)))
                self.ts.delete(r) # since this is destructive delete the tuple from the tuplespace

                return utils.encode(decodeLists(r))
        finally:
            self.lock.release()

    ## \brief If we encounter a deadlock this function is called to unblock a process
    def unblockRandom(self):
        self.blocked_semaphore.acquire()
        try:
            # Get a list of the blocked processes
            l = list(self.blocked_list.keys())
            if len(l) == 0: # if the list is empty we can't do anything...
                return

            # Check each process until we find one that is unblockable
            p, l = l[0], l[1:]
            while not self.blocked_list[p][1]: # this holds a boolean that is true if the process is unblockable
                if len(l) == 0:
                    return # we have no unblockable processes so just bail out
                p, l = l[0], l[1:]

            # Delete the process we're unblocking from the blocked list and send it an unblock message
            del self.blocked_list[p]
            kernel.message(unblock, p)
        finally:
            self.blocked_semaphore.release()

    ## \brief This is called when a process does a collect operation.
    ##
    ## Any matched tuples are removed from the tuplespace
    ## \return A list of tuples matching the pattern
    ## \param pattern The pattern to match the tuples against
    def collect(self, pattern):
        pattern = convertLists(pattern)

        self.lock.acquire()
        try:
            tups = []
            try:
                m = self.ts.matchTuples(pattern) # Create the iterator
                while True: # Keep iterating and adding tuples to the list
                    tups.append(next(m))
            except (NoTuple, StopIteration): # Stop when we get a NoTuple or a StopIteration exception
                for t in tups: # Delete the tuples we've found
                    self.ts.delete(t)
                return list(map(decodeLists, tups)) # return the list of tuples
        finally:
            self.lock.release()

    ## \brief This is called when a process does a copy_collect operation.
    ## \return A list of tuples matching the pattern
    ## \param pattern The pattern to match the tuples against
    def copy_collect(self, pattern):
        pattern = convertLists(pattern)

        self.lock.acquire()
        try:
            tups = []
            try:
                m = self.ts.matchTuples(pattern) # Create the iterator
                while True: # Keep iterating and adding tuples to the list
                    tups.append(next(m))
            except (NoTuple, StopIteration): # Stop when we get a NoTuple or a StopIteration exception
                return list(map(decodeLists, tups)) # return the list of tuples
        finally:
            self.lock.release()

    ## \brief Add a new reference to the tuplespace
    ## \param ref The object that will own the reference
    def addreference(self, ref):
        if self._id == "0:0": # Check we're not the universal tuplespace, which is excluded from garbage collection
            return
        assert not utils.isThreadId(ref)
        self.ref_semaphore.acquire()
        try:
            self.refs.append(ref)
        finally:
            self.ref_semaphore.release()

    ## \brief Remove a reference from the given object to this tuplespace
    ## \param ref The object with the reference
    def removereference(self, ref):
        try:
            if self._id == "0:0": # Check we're not the universal tuplespace, which is excluded from garbage collection
                return
            assert not utils.isThreadId(ref)

            self.ref_semaphore.acquire()
            try:
                try:
                    self.refs.remove(ref) # Remove the reference from the list
                except ValueError: # if the reference doesn't exist then ValueError is raise - and something has gone badly wrong
                    print("!!!%s not in %s for %s" % (ref, str(self.refs), self._id))
                    raise SystemError("Internal reference counting error")
            finally:
                self.ref_semaphore.release()

            # This is just a sanity check to make sure something hasn't gone horribly wrong...
            self.blocked_semaphore.acquire()
            try:
                if ref in list(self.blocked_list.keys()):
                    raise SystemError("Deleting reference for a blocked process " + str(list(self.blocked_list.keys())))
            finally:
                self.blocked_semaphore.release()
        finally:
            self.killlock.release()

        # if a reference is removed this may mean the remaining processes are deadlocked - check if that is the case
        if self.isDeadLocked():
            self.unblockRandom()
        # check to see if we're now garbage
        self.doGarbageCollection()

        return len(self.refs) # return the number of remaining references

    ## \brief Remove all references from the given object to this tuplespace
    ## \param ref The object with the references
    def removeanyreferences(self, ref):
        if self._id == "0:0": # Check we're not the universal tuplespace, which is excluded from garbage collection
            return

        # NOTE:
        # For a long time this system suffered a bug where when a process died it would correctly delete a reference,
        # and then when it actually died the system would clean up any remaining reference with a call to
        # removeanyreferences. In order to allow a proccess to continue the garbage collection for a normal delete reference
        # is done in a new thread, when a process has died this is not necessary and the garbage collection is done in the
        # main thread. This lead to the situation where a removereference would be called, but then because of the way the
        # thread system worked the removeanyreference call, that actually came later, would complete first - and obviosuly
        # this caused an exception.
        # The solution was to have a killlock that is locked before the new thread is created and this causes the
        # removeallreference to block until the removereference has completed.
        #
        self.killlock.acquire()
        try:
            assert utils.isProcessId(ref)

            # This is just a sanity check to make sure something hasn't gone horribly wrong...
            self.blocked_semaphore.acquire()
            try:
                if ref in list(self.blocked_list.keys()):
                    print("ERROR : Deleting references for a blocked process %s" % (str(list(self.blocked_list.keys())), ))
            finally:
                self.blocked_semaphore.release()

            self.ref_semaphore.acquire()
            try:
                try:
                    while True: # Remove all references...
                        self.refs.remove(ref)
                except ValueError: # ... until there are none left and a ValueError is raised.
                    pass
            finally:
                self.ref_semaphore.release()
        finally:
            self.killlock.release()

        # if a reference is removed this may mean the remaining processes are deadlocked - check if that is the case
        if self.isDeadLocked():
            self.unblockRandom()
        # check to see if we're now garbage
        self.doGarbageCollection()

        return len(self.refs) # return the number of remaining references

    ## \brief Check to see if we are not needed by the system
    ##
    ## This function won't actually delete the tuplespace object, that is only done if the number of references falls
    ## to zero - what is does do is empty the tuplespace, causing any reference this tuplespace has to others to be
    ## deleted.
    def doGarbageCollection(self):
        memo = [self._id] # what tuplespaces have we already checked?
        to_check = self.refs[:] # what tuplespaces are left to check?
        while len(to_check) > 0:
            i, to_check = to_check[0], to_check[1:] # get the first on our list
            if i in memo: # if we've already checked it then skip it
                continue

            assert not utils.isThreadId(i)

            if utils.isNodeId(i) or utils.isProcessId(i) or (i == "0:0"):
                # this is either a node, a process or the universal tuplespace so we're still active
                return

            # Extend the to_check list with the other tuplespaces references
            to_check.extend(utils.decode(kernel.message(get_references, i)))

            # Add the tuplespace we've just checked to the memo.
            memo.append(i)

        # If we arrive down here then this tuplespace is part of a clique containing only other tuplespaces

        # Because emptying the tuplespace can cause references to be deleted we do it in another thread to allow us
        # to continue.
        def kill(me):
            me.ts = None
        threading.Thread(target=kill, args=(self, )).start()

    ## \brief Checks to see if there is a deadlock in the system
    def isDeadLocked(self):
        if self._id == "0:0": # The universal tuplespace can never be deadlocked...
            return False

        self.blocked_semaphore.acquire()
        try:
            blocked_thread = list(self.blocked_list.keys()) # what processes are blocked?
        finally:
            self.blocked_semaphore.release()

        notblocked_thread = [] # what processes are apparently unblocked?
        self.ref_semaphore.acquire()
        try:
            process = self.refs[:] # what processes are left to check?
        finally:
            self.ref_semaphore.release()
        checkedts = [self._id] # what tuplespaces have we checked?
        ts = [] # what tuplesspaces are left to check?

        threads = []

        # This works by tracking all the process and tuplespaces in the clique.
        # If the universal tuplespace is in the clique then there cannot be a deadlock.
        # If all processes are blocked on one of the tuplespaces in the clique, and no tuplespace
        # with a reference to a tuplespace inside the clique is outside the clique then a deadlock
        # has occured.
        # The biggest problem is that if a process with a reference to us is blocked on another tuplespace
        # that is also deadlocked then we won't detect it.

        while True:
            if len(threads) > 0:
                tid, threads = threads[0], threads[1:]

                if tid in blocked_thread:
                    continue
                elif tid not in notblocked_thread:
                    notblocked_thread.append(tid)

            elif len(process) > 0:
                pid, process = process[0], process[1:]

                if utils.isTupleSpaceId(pid): # this is actually a tuplespace so add it to that list
                    ts.append(pid)
                    continue
                elif utils.isNodeId(pid):
                    return False
                else:
                    threads.extend(utils.decode(kernel.message(get_threads, pid)))

            elif len(ts) > 0:
                tid, ts = ts[0], ts[1:]
                if tid == "0:0": # the universal tuplespace means we cannot be deadlocked
                    return False
                elif tid in checkedts: # if we've already checked it then skip it
                    continue

                checkedts.append(tid)

                # get the references and blocked processes for this tuplespace
                refs = utils.decode(kernel.message(get_references, tid))
                blocked = utils.decode(kernel.message(get_blocked_list, tid))

                blocked_thread.extend(blocked)
                process.extend(refs)
                for tid in blocked: # for each process that is blocked on the tuplespace we're checking..
                    if tid in notblocked_process: #..check we haven't marked as not blocked..
                        del notblocked_thread[notblocked_thread.index(tid)] #.. and if we have mark it as blocked
            else:
                break

        return (len(notblocked_thread) == 0) # If there no unblocked processes then we're deadlocked

from . import utils
