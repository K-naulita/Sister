#!/bin/sh

# Important: you first need to install linda. The source code in the
# directory linda-0.6, with instructions. You may need to run
#
# python setup.py install
#
# with administrative permissions

echo "This code runs only with python2!"

linda_server > /dev/null 2>&1 & 

echo "Waiting until server started"
sleep 2

python alice.py &
python bob.py &
python chuck.py &

# kill the server
kill `ps -ax | awk '/[l]inda_server/{print $1}'`

