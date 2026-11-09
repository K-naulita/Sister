#!/usr/bin/python

import linda
import time
linda.connect()

min         = 100
max         = 200
tests       = 100
msg         = "x" * min
lenVector   = list(range(min,max+1))
timeVector  = []

for i in range(max-min+1):
    startTime = time.time()
    for j in range(0, tests):
        linda.universe._out((1, msg))
        returnMsg = linda.universe._in((str, 1))
    stopTime = time.time()
    averageTime = (stopTime-startTime)/tests
    timeVector.append(averageTime)
    msg = msg + "x"

print(timeVector)
print([1.0/x for x in timeVector])

