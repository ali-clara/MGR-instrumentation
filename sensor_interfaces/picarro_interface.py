# -------------
# Establishes serial communication with the Picarro spectrograph. Currently has only been tested on the G2401 model 
# that measures gas concentrations, but should work with any Picarro that supports a Remote Command Interface. The Picarro 
# must be properly configured (Picarro Utilities > Setup Tool > Port Manager) to enable the interface, see README for full docs
#
# Ali Jones
# Last updated 9/4/24
# -------------

import serial
from serial import SerialException
import time

import logging
from logdecorator import log_on_start , log_on_end , log_on_error

# Set up a logger for this module
logger = logging.getLogger(__name__)
# Set the lowest-severity log message the logger will handle (debug = lowest, critical = highest)
logger.setLevel(logging.DEBUG)
# Create a handler that saves logs to the log folder named as the current date
fh = logging.FileHandler(f"logs\\{time.strftime('%Y-%m-%d', time.localtime())}.log")
# fh = logging.StreamHandler()
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)
# Create a formatter to specify our log format
formatter = logging.Formatter("%(levelname)s: %(asctime)s - %(name)s:  %(message)s", datefmt="%H:%M:%S")
fh.setFormatter(formatter)

class Picarro():
    def __init__(self, serial_port="COM3", baud_rate=19200) -> None:
        # Picarro communication codes
        self.QUERY = b"_Meas_GetConcEx\r\n" # gets latest measurement and timestamp
        # self.QUERY = b'_Meas_GetConc\r\n' # gets latest measurement and timestamp
        self.STATUS = b'_Instr_GetStatus\r\n' # gets instrument status

        self.initialize_pyserial(serial_port, baud_rate)

    def __del__(self) -> None:
        """Deconstructor, closes the serial port when this object is destroyed"""
        self.ser.close()

    def initialize_pyserial(self, port, baud):
        """
        Method to open the serial port at the specified baud. Also specifies a timeout to prevent infinite blocking.
        These values (except for timeout) MUST match the instrument. Typing "mode" in the Windows Command Prompt 
        gives information about serial ports, but sometimes the baud is wrong, so beware. Check sensor documentation.
        Inputs - port (str, serial port), baud (int, baud rate)
        """
        try:
            self.ser = serial.Serial(port, baud, timeout=0.5)
            logger.info(f"Connected to serial port {port} with baud {baud}")
            # print(self.ser.writable())
            # print(self.ser.readable())
            # print(self.ser.BAUDRATES)
        except SerialException:
            logger.warning(f"Could not connect to serial port {port}")

    def initialize_picarro(self, timeout=10):
        """
        Queries the picarro until we get a valid output. If we can't get a valid reading after a set of attempts,
        report that initialization failed.
        
        The initialization methods return one of three values: 
        1 (real hardware, succeeded), 2 (simulated hardware), 3 (failed to initialize/error)
        """
        # Try to query and get a valid output. If we can't get a valid reading after a set of attempts, report back that initialization failed 
        try:
            for i in range(timeout):
                logger.info(f"Initialization attempt {i+1}/{timeout}")
                timestamp, data_out = self.query()
            
                # Validity check - should return a list with 5 elements
                if type(timestamp) == float and len(data_out) == 5:
                    logger.info("Picarro initialized")
                    return 1

        except Exception as e:
            logger.info(f"Exception in Picarro initialization: {e}")

        logger.info(f"Picarro initialization failed after {timeout} attempts")
        return 3
    
    def _read_picarro(self):
        """Method to write the command and read back one byte at a time until an end character is reached.
            There might be an existing method that does this, but nether readline() nor read_until() did the trick.
            
            Inputs - command (byte str with appropriate terminator)\n
            Returns - buf (byte str)"""
        
        # Read the command into a buffer until we get the closing character ("\r" in binary) or we timeout (>70 loops, 
        # the picarro usually returns 51 bytes so that should be sufficient)
        buf = b''
        char = b''
        timeout = 0
        while char != b'\r' and timeout <= 10: #changed from 70
            char = self.ser.read(1)
            buf = buf + char
            timeout += 1

        logger.info(f"read {timeout} bytes")
        # Check if there was an error (stored in the first 4 chars of the buffer)
        if buf[:4] == "ERR:":
            raise Exception(f"Error in Picarro communication: {buf}")
        else:
            return buf

    @log_on_end(logging.INFO, "Picarro queried", logger=logger)
    def query(self):
        """
        Queries the picarro to get the most recent measurement and timestamp. The first element of the query 
        is the time, and the rest are gas or isotope concentrations. As the Picarro is set up currently, they're
        in the order ["CO2"; "CH4"; "CO"; "H2O"] for gas and [] for water. Either way, we can split them along ";"

            Returns - timestamp (float, epoch time), output (str)
        """
        # Write the command
        print("trying with readline")
        self.ser.write(self.QUERY)
        print(self.ser.readline())

        print("trying with read_until")
        self.ser.write(self.QUERY)
        print(self.ser.read_until(b'\n\r'))
        
        print("trying with custom")
        self.ser.write(self.QUERY)
        output = self._read_picarro()
        print(output)

        output = output.decode()
        timestamp = time.time()
        # Split along the semicolons
        output = output.split(";")
        
        return timestamp, output
    

if __name__ == "__main__":
    my_picarro = Picarro(serial_port="COM7", baud_rate=9600)
    # order of the gas measurements returned by query()
    #   I had to manually watch the picarro and the serial output to determine this order, not sure where it's specified
    gasses = ["CO2", "CH4", "CO", "H2O"]

    isotopes = ["H20", "Delta_18", "Delta_D"]

    ## ------- UNIT TESTING  ------- ##
    stop = False
    while not stop:
        command = input("a: Query, x: Quit \n")
        if command == "a" or command == "A":
            timestamp, output = my_picarro.query()
            sample_time = output[0] # the time at which the measurement was sampled, probably different than timestamp
            print("Measurement time: ", sample_time)
            print("My timestamp: ", timestamp)
            print(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)))
            for i, value in enumerate(output[1:]): # the gas concentrations
                print(f"data: ", value)
        elif command == "x" or command == "X":
            stop = True
        else:
            print("Invalid entry. Please try again")
