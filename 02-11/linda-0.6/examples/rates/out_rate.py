#!/usr/bin/python

import linda
from time import time, sleep

linda.connect()

def total(rate):
    if rate < 0:
        return 0
    else:
        return rate + total(rate - 10)

start = time()
sleep(1)

for msg in xrange(total(1501)):
    linda.universe._out((msg, ))
    linda.universe._in((msg, ))

    sleep(1.0 / (int(time() - start) * 10))

