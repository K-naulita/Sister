import sys, Ice
import Demo
 
communicator = Ice.initialize(sys.argv) as communicator

base = communicator.stringToProxy("SimplePrinter:default -p 11000")
printer = Demo.PrinterPrx.checkedCast(base)
if not printer:
    raise RuntimeError("Invalid proxy")

printer.printString("Hello World!")
