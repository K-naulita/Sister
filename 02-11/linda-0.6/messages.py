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

## \namespace messages
## \brief This contains the definitions for the messages used to communicate internally.
##
## \author Andrew Wilkinson <aw@cs.york.ac.uk>

done = "done" # Generic ok message
dont_know = "dont_know" # Don't know the answer

register_process = "register_process" # Sent by a client process to get an id
register_thread = "register_thread" # Sent by a client thread to get an id
unregister_thread = "unregister_thread" # Sent by a client thread to get an id
unregister_process = "unregister_process" # Sent by a client just before it disconnects

my_name_is = "my_name_is" # If a server connects and already has an idea then this is sent

create_tuplespace = "create_tuplespace" # Sent by a client to create a tuplespace

get_connect_details = "get_connection_details" # Sent to find out how to connect to a server

get_new_node_id = "get_new_node_id" # Sent by a new server
get_node_id = "get_node_id" # Asks the destination server what it's id is

read_tuple = "read_tuple" # Sent by a client process to read a tuple
in_tuple = "in_tuple" # Sent by a client process to in a tuple
out_tuple = "out_tuple" # Sent by a client process to out a tuple
unblock = "unblock" # Return message to unblock a client process

return_tuple = "return_tuple" # Return message when a tuple is being returned

collect = "collect" # Sent by a client process to collect tuples
copy_collect = "copy_collect" # Sent by a client process to copy tuples

multiple_in = "multiple_in" # Internal message to move a group of tuples

increment_ref = "increment_ref" # Sent to increment the reference count of a tuple space
decrement_ref = "decrement_ref" # Sent to decrement the reference count of a tuple space

get_references = "get_references" # Get all references to a tuplespace
get_neighbours = "get_neighbours" # Get all neighbours to a server
know_server = "know_server" # Asks whether the server knows the details for a server
get_blocked_list = "get_blocked_list" # Get all processes blocked on a tuplespace
get_threads = "get_threads" # Get all threads in a process

get_stats = "get_stats" # Get the stats for a server

not_permitted = "not_permitted" # Action not permitted (not currently used - reserved for capablity linda)

kill_server = "kill_server"

support_domain = "support_domain"
support_shm = "support_shm"
begin_session = "begin_session"

yes = "yes"
no = "no"

close_connection = "close_connection"
