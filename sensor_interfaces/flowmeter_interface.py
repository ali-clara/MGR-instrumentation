import serial
from serial import SerialException
import time
import pandas as pd
import numpy as np
import yaml

import logging
from logdecorator import log_on_start , log_on_end , log_on_error

logger = logging.getLogger(__name__) # set up a logger for this module
logger.setLevel(logging.DEBUG) # set the lowest-severity log message the logger will handle (debug = lowest, critical = highest)
ch = logging.StreamHandler() # create a handler
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(levelname)s: %(asctime)s - %(name)s:  %(message)s", datefmt="%H:%M:%S")
ch.setFormatter(formatter)
logger.addHandler(ch)

class FlowMeter():
    def __init__(self, serial_port="COM6", baud_rate=115200) -> None:
        """
        Class to communicate with Sensirion flow meters. It has been tested on the SLI-2000 and the SLS-1500, 
        which both use the SF04 chip. Not sure if it would work with other models, especially the SF06 chip, but maybe.
        Differences between the two models show up in data processing (scale factor and output units) but not in communication.
        """
        # Flowmeter communication codes
        self.START = bytes([0x7e, 0x0, 0x33, 0x2, 0x0, 0x64, 0x66, 0x7e])
        self.QUERY =  bytes([0x7e, 0x0, 0x35, 0x1, 0x0, 0xc9, 0x7e])

        # The flowmeter returns "~" at the end of its string. Unfortunately it also returns this at the start of its string, 
        # so we have to be a little clever about reading in the data
        self.END_CHAR = b'~' 
        
        self.initialize_pyserial(serial_port, baud_rate)

    def __del__(self) -> None:
        """Deconstructor, closes the serial port when the object is destroyed"""
        self.ser.close()

    def initialize_pyserial(self, port, baud):
        """
        Method to open the serial port at the specified baud. Also specifies a timeout to prevent infinite blocking.
        These values (except for timeout) MUST match the instrument. Typing "mode" in the Windows Command Prompt 
        gives information about serial ports, but sometimes the baud is wrong, so beware. Check sensor documentation.
        Inputs - port (str, serial port), baud (int, baud rate)
        """
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            logger.info(f"Connected to serial port {port} with baud {baud}")
        except SerialException:
            logger.info(f"Could not connect to serial port {port}")

    @log_on_end(logging.INFO, "Flowmeter measurements started", logger=logger)
    def start_measurement(self):
        """Method to start instrument"""
        self.ser.write(self.START)

    @log_on_end(logging.INFO, "Flowmeter measurements stopped", logger=logger)
    def stop_measurement(self):
        """Not sure if this command exists, leaving it here as a reminder to myself to check"""
        pass

    def _read_flowmeter(self):
        """Method to read back one byte at a time until an end character (self.END_CHAR) is reached. The flowmeter returns "~" at the end of its string; 
        unfortunately, it also returns this at the start of its string. To get the full sequence, we read until we've recieved two tildes, and then stop reading.
            
            Returns - buf (byte str)"""
        
        # Read the command into a buffer until we get two closing characters ("~" in binary) or we timeout (>50 bytes read)
        buf = b''
        timeout = 0
        num_end_chars = 0
        while num_end_chars < 2 and timeout <= 50:
            # Read a byte and append to buffer
            char = self.ser.read(1)
            buf = buf + char
            # Keep track of how many times we've gone through the loop
            timeout += 1
            # Keep track of how many "~" we've recieved
            if char == self.END_CHAR:
                num_end_chars += 1

        return buf
        
    
    @log_on_end(logging.INFO, "Flowmeter queried", logger=logger)
    def query(self):
        """Queries the flowmeter. Returns raw data and timestamp
            Returns - timestamp (float, epoch time), data_out ([int], raw flowmeter reading)"""
        time1 = time.time()
        self.ser.write(self.QUERY)
        timestamp = time.time()
        response = self._read_flowmeter()
        time2 = time.time()
        print(response)
        print(f"sending serial message took {timestamp-time1} sec")
        print(f"flowmeter reading took {time2-timestamp} sec")
        # Decode the response
        data_out = [int(byte) for byte in response]
        return timestamp, data_out
    
if __name__ == "__main__":
    ## ------- DATA PROCESSING FUNCTIONS FOR TESTING  ------- ##
    def bytepack(byte1, byte2):
        # concatenates 2 uint8 bytes to uint16 and takes two's complement if negative
        binary16 = (byte1 << 8) | byte2
        return binary16
    
    def twos(binary):
        # takes two's complement of binary input if negative
        # returns input if not negative
        if (binary & (1 << 15)):
            n = -((binary ^ 0xFFFF) + 1)
        else:
            n = binary
        return n
    
    def check_flow_data(rawdata):
        # This comes from Abby. I should ask her about it       
        try:
            adr = rawdata[1]
            cmd = rawdata[2]
            state = rawdata[3]
            if state != 0:
                raise Exception("Bad reply from flow meter")
            length = rawdata[4]
            rxdata8 = rawdata[5:5 + length]
            chkRx = rawdata[5 + length]

            chk = hex(adr + cmd + length + sum(rxdata8))  # convert integer to hexadecimal
            chk = chk[-2:]  # extract the last two characters of the string
            chk = int(chk, 16)  # convert back to an integer base 16 (hexadecimal)
            chk = chk ^ 0xFF  # binary check
            if chkRx != chk:
                raise Exception("Bad checksum")

            rxdata16 = []
            if length > 1:
                i = 0
                while i < length:
                    rxdata16.append(bytepack(rxdata8[i], rxdata8[i + 1]))  # convert to a 16-bit integer w/ little-endian byte order
                    i = i + 2  # +2 for pairs of bytes

            return adr, cmd, state, length, rxdata16, chkRx

        except Exception as e:
            print(f"Encountered exception in validation: {e}. Skipping this data.")
            return False

    def process_flow_data(raw_data, timestamp, scale_factor):
        # Checks if data is valid (function above) and if so extracts flow rate
        validated_data = check_flow_data(raw_data)
        try:
            if validated_data:
                rxdata = validated_data[4]
                ticks = twos(rxdata[0])
                flow_rate = (ticks / scale_factor)

                d = {"time (epoch)": [timestamp], "flow": [flow_rate]}
                output = pd.DataFrame(d)
                return output
        except Exception as e:
            print(f"Encountered exception in processing: {e}. Skipping this data")

    ## ------- UI INTEFACE FOR TESTING  ------- ##
    with open("config/sensor_comms.yaml", 'r') as stream:
        comms_config = yaml.safe_load(stream)

    print("Testing Flowmeter serial communication\n")
    valid_scale_factor = False
    while not valid_scale_factor:
        device = input("Which device? 1: SLI-2000 (green), 2: SLS-1500 (black)\n")
        if device == "1":
            scale_factor = 5
            port = comms_config["Flowmeter SLI2000 (Green)"]["serial port"]
            baud = comms_config["Flowmeter SLI2000 (Green)"]["baud rate"]
            print("Device set to SLI-2000: units uL/min, scale factor 5")
            valid_scale_factor = True
        elif device == "2":
            scale_factor = 500
            port = comms_config["Flowmeter SLS1500 (Black)"]["serial port"]
            baud = comms_config["Flowmeter SLS1500 (Black)"]["baud rate"]
            print("Device set to SLS-1500: units mL/min, scale factor 500")
            valid_scale_factor = True
        else:
            print("Invalid entry. Please try again")

    my_flow = FlowMeter(serial_port=port, baud_rate=baud)

    stop = False
    while not stop:
        command = input("a: Start measurement, b: Stop measurement, c: Query, x: Quit \n")
        if command == "a" or command == "A":
            my_flow.start_measurement()
        elif command == "b" or command == "B":
            pass
        elif command == "c" or command == "C":
            timestamp, raw_output = my_flow.query()
            print(raw_output)
            print(type(raw_output[0]))
            procssed_output = process_flow_data(raw_output, timestamp, scale_factor)
            print(procssed_output)
        elif command == "x" or command == "X":
            stop = True
        else:
            print("Invalid entry. Please try again")