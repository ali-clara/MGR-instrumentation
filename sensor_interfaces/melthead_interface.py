import serial
from serial import SerialException
import time
import yaml
import crcmod

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
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)
# Create a formatter to specify our log format
formatter = logging.Formatter("%(levelname)s: %(asctime)s - %(name)s:  %(message)s", datefmt="%H:%M:%S")
fh.setFormatter(formatter)


class MeltHead:
    def __init__(self, serial_port="COM7", baud_rate=38400) -> None:
        self.initialize_pyserial(serial_port, baud_rate)

        self.AUTO = bytes.fromhex("55 FF 05 10 03 00 09 46 01 04 08 01 01 0F 01 00 0A 38 7C")
        self.OFF = bytes.fromhex("55 FF 05 10 03 00 09 46 01 04 08 01 01 0F 01 00 3E 9F 0B")

        self.melthead_on = False

    def __del__(self):
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
    
    @log_on_start(logging.INFO, "Initializing Melthead", logger=logger)
    def initialize_pid(self, timeout):
        """
        I don't have a great way to verify the Melthead is working as expected since I don't have full comms, all 
        I can do is see if we're reading data and can decode it properly.
        
        The initialization methods return one of three values: 
        1 (real hardware, succeeded), 2 (simulated hardware), 3 (failed to initialize/error)
        """

        for _ in range(timeout):
            try:
                result = self.ser.read_until()
                result_decoded = result.hex()
                if type(result_decoded) == str and len(result_decoded) > 1:
                    logger.info("Melthead initialized")
                    return 1
            except Exception as e:
                logger.info(f"Encountered exception in Melthead initialization: {e}")
            
        return 3

    def query(self):
        pass

    def calc_data_crc(self, string):
        """Method that calculates the Cyclic Redundancy Check (crc) for the data string. In short, a CRC is an operation that's
        done to a bytestring to make sure the data hasn't been corrupted. If this doesn't make sense, that's totally fine. It
        barely makes sense to me, and I wrote it.

        Args:
            string (str): String of hex bytes we need to validate before sending to the instrument

        Returns:
            str: Two crc hex bytes in the correct order to be appended to the command
        """
        string_encoded = bytes.fromhex(string)
        # Make the crc function. This is from https://reverseengineering.stackexchange.com/questions/8303/rs-485-checksum-reverse-engineering-watlow-ez-zone-pm
        crc_func = crcmod.mkCrcFun(0x11021, 0, True, 0xFFFF)
        # Apply the crc function to our hex string. Returns something in the form "0xHHHH"
        crc = hex(crc_func(string_encoded))
        # Trim off the "0x", that's just identifying it as hexadecimal
        crc = crc[2:]
        # This doesn't preserve leading zeros. If we've lost the leading zero, add it back here
        if len(crc) < 4:
            crc = '0' + crc
        # Isolate the two bits we need. We need to return them "little endian", so flip the order in which they were given
        bit1 = crc[2:]
        bit2 = crc[0:2]
        # Finally, concatenate and return
        return bit1+bit2
    
    def c_to_f(self, tempc):
        """Converts celsius to fahrenheit"""
        return (tempc * 9/5) + 32
    
    def validate_setpoint(self, setpoint):
        """Method to make sure we're giving the controller a valid reading and that it's within acceptable temperature bounds"""
        valid_setpoint = False
        try:
            setpoint = float(setpoint)
        # If we're passed a string that we can't parse, we'll get a ValueError. If we're passed a Nonetype or other input 
        # we can't convert to a float, we'll get a TypeError. Catch both.
        except (ValueError, TypeError) as e:
            logger.info(f"Invalid melthead setpoint: {setpoint}. {e}")
        except Exception as e:
            logger.info(f"Not sure how you managed to trigger this error, nicely done! Invalid melthead setpoint: {setpoint}. {e}")
            return False
        else:
            if setpoint < 25:
                valid_setpoint = True

        return valid_setpoint, setpoint
    
    def send_setpoint(self, setpoint):
        """Method to compile and send the setpoint command for the given melthead temperature. The PID module takes 
        serial commands in BACnet form, which is where most of these parameters come from.

        Args:
            setpoint (float): Desired melthead setpoint, in degC
        """
        setpoint_valid, setpoint = self.validate_setpoint(setpoint)
        if setpoint_valid:
            # Assemble the first parts of the message
            preamble = '55 FF' 
            frame_type = '05'
            destination_address = '10' 
            source_address = '00' 
            length = '00 0A'
            # This crc depends on the previous bits, so is constant for setpoint messages. Would NOT be this value if you sent something else
            header_crc = 'EC' 
            # Not sure what this is exactly - I think it encodes which channel in the device we're sending the command to
            #  (i.e setpoint and not heater power), but it could mean other things as well
            setpoint_command = '01 04 07 01 01 08'
            # Convert to fahrenheit, since that's what the device takes
            setpoint_f = self.c_to_f(setpoint)
            # Convert from a floating point to IEEE hexadecimal format
            setpoint_data = ieee754_conversions.dec_to_hex(setpoint_f)
            # Finally, calculate the CRC for our data
            data_crc = self.calc_data_crc(setpoint_command+setpoint_data)
            # Assemble the message in order
            cmd = preamble+frame_type+destination_address+source_address+length+header_crc+setpoint_command+setpoint_data+data_crc
            print(cmd)
            # Convert it to bytes
            cmd = bytes.fromhex(cmd)
            # And, finally, write it to the device
            self.ser.flush()
            self.ser.write(cmd)

            logger.info(f"Set setpoint to {setpoint} degC")
        else:
            return

    def start_control_loop(self):
        """Method to start the PID control loop"""
        self.ser.write(self.AUTO)
        self.melthead_on = True

    def stop_control_loop(self):
        """Method to stop the PID control loop. The controller currently has no active cooling set (though it
        does have that capability), so this just turns off the power and lets the temp regulate on its own"""
        self.ser.write(self.OFF)
        self.melthead_on = False

if __name__ == "__main__":

    ## ------- UI INTEFACE FOR TESTING  ------- ##
    with open("config/sensor_comms.yaml", 'r') as stream:
        comms_config = yaml.safe_load(stream)

    port = comms_config["Melthead"]["serial port"]
    baud = comms_config["Melthead"]["baud rate"]

    mymelt = MeltHead(serial_port=port, baud_rate=baud)

    print("Testing melthead (EZ-ZONE) serial communication\n")
    stop = False
    while not stop:
        command = input("a: Initialize, b: Start control loop, c: Stop control loop, d: Send setpoint, x: Quit \n")
        if command == "a" or command == "A":
            mymelt.initialize_pid()
        elif command == "b" or command == "B":
            mymelt.start_control_loop()
        elif command == "c" or command == "C":
            mymelt.stop_control_loop()
        elif command == "d" or command == "D":
            setpoint = input("Enter setpoint (degC):")
            try:
                float(setpoint)
            except:
                print("Could not convert given setpoint to a float. Please try again")
            else:
                mymelt.send_setpoint(float(setpoint))
        elif command == "x" or command == "X":
            stop = True
        else:
            print("Invalid entry. Try again")
