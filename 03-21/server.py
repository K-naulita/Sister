import sys, Ice
import Demo
 
class PrinterI(Demo.Printer):
    def printString(self, s, current=None):
        print(s)

communicator = Ice.initialize(sys.argv) 

adapter = communicator.createObjectAdapterWithEndpoints("SimpleAdapter", "default -p 11000")
object = PrinterI()
adapter.add(object, communicator.stringToIdentity("SimplePrinter"))
adapter.activate()

communicator.waitForShutdown()