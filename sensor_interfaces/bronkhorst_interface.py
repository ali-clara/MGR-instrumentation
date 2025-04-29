import serial
from serial import SerialException
import time
import yaml
import numpy as np

try:
    import ieee754_conversions
except ImportError:
    import pathlib
    import sys
    _parentdir = pathlib.Path(__file__).parent.parent.resolve()
    sys.path.insert(0, str(_parentdir))
    import ieee754_conversions
    sys.path.remove(str(_parentdir))

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

class Bronkhorst():
    def __init__(self, serial_port="COM3", baud_rate="38400") -> None:
        # Bronkhorst communication codes
        self.GET_MEAS = b':06030401210120\r\n' # gets the measurement as a percent of the total (0-32000 => 0-100%)
        self.GET_FMEAS = b':06800421402140\r\n' # gets the measurement as a float
        self.GET_FSETPOINT = b':06800421412143\r\n' # gets the setpoint in mBAR
        self.GET_TEMP = b':06800421472147\r\n' # gets the temp as a float
        self.GET_UNIT = b':078004017F017F07\r\n' # gets the unit as a string

        self.GET_SETPOINT_MEAS = b':0A80048121012101210120\r\n' # chained request to get the measurement (0-32000) and setpoint (0-32000)
        self.GET_FMEAS_TEMP =    b':0A8004A140214021472147\r\n' # chained request to get the fmeasure (float) and temp (float)
        
        self.initialize_pyserial(serial_port, baud_rate)

        self.fmeasure_unit = ""

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
        except SerialException:
            logger.warning(f"Could not connect to serial port {port}")

    def get_unit(self):
        self.ser.write(self.GET_UNIT)
        output = self.ser.read_until(b'\r\n').decode()
        return output

    def validate_setpoint(self, setpoint):
        """Method to make sure we're giving the controller a valid reading and that it's within acceptable pressure bounds"""
        valid_setpoint = False
        try:
            setpoint = float(setpoint)
        # If we're passed a string that we can't parse, we'll get a ValueError. If we're passed a Nonetype or other input 
        # we can't convert to a float, we'll get a TypeError. Catch both.
        except (ValueError, TypeError) as e:
            logger.info(f"Invalid bronkhorst setpoint: {setpoint}. {e}")
        except Exception as e:
            logger.info(f"Not sure how you managed to trigger this error, nicely done! Invalid bronkhorst setpoint: {setpoint}. {e}")
            return False
        else:
            # if within some pressure bound:
                # do a thing
            valid_setpoint = True

        return valid_setpoint, setpoint
    
    def send_setpoint(self, setpoint):
        """Converts a floating point value setpoint to IEEE754 hexadecimal representation and sends
        it to the Bronkhorst.

        Args:
            setpoint (float): Pressure setpoint in mBar to send to the Bronkhorst
        """
        setpoint_valid, setpoint = self.validate_setpoint(setpoint)
        if setpoint_valid:
            # Convert the setpoint to the proper format (hexadecimal IEEE754 representation)
            hex_representation = ieee754_conversions.dec_to_hex(setpoint)
            # Combine the setpoint data with the rest of the command string
            self.SEND_SETPOINT = b':0880012143'+(hex_representation).encode()+b'\r\n'
            # Send it
            self.ser.write(self.SEND_SETPOINT)
            # Read to clear the input buffer
            self.ser.read_until(b'\n').decode()
            print(f"sent setpoint {self.SEND_SETPOINT}")
        else:
            print("setpoint not valid")
    
    def initialize_bronkhorst(self, timeout=10):
        """
        Queries the bronkhorst until we get a valid output. If we can't get a valid reading after a set of attempts,
        report that initialization failed.

        The initialization methods return one of three values:
        1 (real hardware, succeeded), 2 (simulated hardware), 3 (failed to initialize / error)
        """

        # Try to query to get a valid output. If we can't get a valid reading after a set of attempts, report back that initialization failed
        try:
            for i in range(timeout):
                logger.info(f"Initialization attempt {i+1}/{timeout}")
                # grab the device units
                unit = self.get_unit()
                unit = unit[13:]
                self.fmeasure_unit = bytearray.fromhex(unit).decode().strip()
                # grab the device measurements
                timestamp, output = self.query()
                fsetpoint, meas, fmeas_and_temp = output
                # Check if the measurements are the lengths we expect and the timestamp is the type we expect
                if len(fsetpoint) == 21 and len(meas) == 17 and len(fmeas_and_temp) == 33 and type(timestamp) == float:
                    logger.info("Bronkhorst initialized")
                    return 1
                
        except Exception as e:
            logger.warning(f"Exception in Bronkhorst initialization: {e}")

        logger.warning(f"Bronkhorst failed to initialize after {timeout} attempts")
        return 3
    
    def query(self):
        """
        Method to query the Bronkhorst.
            
            Returns - 
                - timestamp: float, epoch time
                - output: ((bytestr, bytestr, bytestr), responses for fsetpoint, measure, and a
                chained response for fmeasure & temperature)
        """
        self.ser.write(self.GET_FSETPOINT)
        fsetpoint = self.ser.read_until(b'\r\n').decode()
        self.ser.write(self.GET_MEAS)
        meas = self.ser.read_until(b'\r\n').decode()
        self.ser.write(self.GET_FMEAS_TEMP)
        fmeas_and_temp = self.ser.read_until(b'\r\n').decode()
        timestamp = time.time()

        output = (fsetpoint, meas, fmeas_and_temp)
        
        return timestamp, output
    
if __name__ == "__main__":
    ## ------- DATA PROCESSING FUNCTION FOR TESTING  ------- ##
    def mantissa_to_int(mantissa_str):
        """Method to convert the mantissa of the IEEE floating point to its decimal representation"""
        # Variable to be our exponent as we loop through the mantissa
        power = -1
        # Variable to store the decimal value of mantissa
        mantissa = 0
        # Iterate through binary number and convert it from binary
        for i in mantissa_str:
            mantissa += (int(i)*pow(2, power))
            power -= 1
            
        return (mantissa + 1)

    def hex_to_ieee754_dec(hex_str:str) -> float:
        """
        Method to convert a hexadecimal string (e.g what is returned from the Bronkhorst) into an IEEE floating point. It's gnarly,
        more details https://www.mimosa.org/ieee-floating-point-format/ and https://www.h-schmidt.net/FloatConverter/IEEE754.html
        
        In short, the IEEE 754 standard formats a floating point as N = 1.F x 2E-127, 
        where N = floating point number, F = fractional part in binary notation, E = exponent in bias 127 representation.

        The hex input corresponds to a 32 bit binary:
                Sign | Exponent  |  Fractional parts of number
                0    | 00000000  |  00000000000000000000000
            Bit: 31   | [30 - 23] |  [22        -         0]

        Args - 
            - hex_str (str, hexadecmial representation of binary string)

        Returns -
            - dec (float, number in decimal notation)
        """

        # Convert to integer, keeping its hex representation
        ieee_32_hex = int(hex_str, 16)
        # Convert to 32 bit binary
        ieee_32 = f'{ieee_32_hex:0>32b}'
        # The first bit is the sign bit
        sign_bit = int(ieee_32[0])
        # The next 8 bits are exponent bias in biased form
        exponent_bias = int(ieee_32[1:9], 2)
        # Subtract 127 to get the unbiased form
        exponent_unbias = exponent_bias - 127
        # Next 23 bits are the mantissa
        mantissa_str = ieee_32[9:]
        mantissa_int = mantissa_to_int(mantissa_str)
        # Finally, convert to decimal
        dec = pow(-1, sign_bit) * mantissa_int * pow(2, exponent_unbias)

        return dec
    
    def process_output(output, timestamp, unit):
        """Method to process Bronkhorst output when querying setpoint/measurement and fmeasure/temperature, modify if
        we add query values. I /really/ didn't want to write a general function for any potential bronkhorst return"""

        fsetpoint, measure, fmeas_and_temp = output

        # Parsing measurement is straightforward - 
        # First, slice the setpoint and measurement out of the chained response and convert the hex string to an integer
        measure = int(measure[11:15], 16)
        # Then, scale the raw output (an int between 0-32000) to the measurement signal (0-100%)
        measure = np.interp(measure, [0,41942], [0,131.07]) # This is basically the same as the setpoint, but can measure over 100%

        # Parsing fsetpoint, fmeasure and temperature is a little more complicated -
        # grab their respective slices from the chained response, then convert from IEEE754 floating point notation to decimal
        fsetpoint = ieee754_conversions.dec_from_hex(fsetpoint[11:19])
        fmeasure = ieee754_conversions.dec_from_hex(fmeas_and_temp[11:19])
        temp = ieee754_conversions.dec_from_hex(fmeas_and_temp[23:])
    
        print(timestamp)
        print(f"Setpoint: {fsetpoint} {unit}")
        print(f"Measurement: {measure}%")
        print(f"Fmeasure: {fmeasure} {unit}")
        print(f"Temperature: {temp}°C")

    ## ------- UI FOR TESTING  ------- ##
    with open("config/sensor_comms.yaml", 'r') as stream:
        comms_config = yaml.safe_load(stream)
    port = comms_config["Bronkhorst Pressure"]["serial port"]
    baud = comms_config["Bronkhorst Pressure"]["baud rate"]

    my_bronkhorst = Bronkhorst(serial_port=port, baud_rate=baud)
    
    print("Testing serial communication\n")
    stop = False
    while not stop:
        command = input("a: Initialize bronkhorst, b: Check unit, c: Query, d: Send Setpoint, x: Quit \n")
        if command == "a" or command == "A":
            my_bronkhorst.initialize_bronkhorst()
        elif command == "c" or command == "C":
            timestamp, output = my_bronkhorst.query()
            unit_ascii = my_bronkhorst.fmeasure_unit
            process_output(output, timestamp, unit_ascii)
        elif command == "b" or command == "B":
            output = my_bronkhorst.get_unit()
            unit = output[13:]
            unit_ascii = bytearray.fromhex(unit).decode().strip()
            print(f"Bronkhorst returning measurements in {unit_ascii}")
        elif command == "d" or command == "D":
            setpoint = input("Setpoint: ")
            my_bronkhorst.send_setpoint(setpoint)
            
        elif command == "x" or command == "X":
            stop = True
        else:
            print("Invalid entry. Try again")




