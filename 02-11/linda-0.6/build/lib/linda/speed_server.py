#!/usr/bin/python

import linda
linda.connect()

while(1):
        t = linda.universe._in((1,str))
        linda.universe._out((t[1],1))
