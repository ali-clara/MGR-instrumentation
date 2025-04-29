# -------------
# This script creates shadow hardware. If you're not connected to the instruments, this can substitute sensor readings
# with simulated values that have the same representation and type as real data 
# 
# Ali Jones
# Last updated 9/28/24
# -------------

import time
import numpy as np
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

# Global variable crimes! Tried to keep this pretty minor - set up a global flag to let us know if we're in
# "debug" mode or not - if we are, our simulated sensors return valid (if fake) sensor readings, so we can
# check processing, saving, plotting, etc. If we aren't in debug mode, they return NAN. We default to False.
global debug 
debug = False
def setSimDebugMode(use_debug):
    global debug
    if use_debug:
        debug = True

def getSimDebugMode():
    global debug
    return debug

# Create classes that mirror the real sensor interfaces

class Abakus():
    def __init__(self, serial_port="COM3", baud_rate=38400) -> None:
        """Fake hardware, pretends to do everything the real Abakus class does"""
        self.initialize_pyserial(serial_port, baud_rate)

    def __del__(self) -> None:
        self.stop_measurement()

    def initialize_pyserial(self, port, baud):
        logger.info(f"Fake hardware, pretending to use serial port {port} with baud {baud}")

    @log_on_start(logging.INFO, "Initializing Abakus")
    def initialize_abakus(self):
        """
        The initialization methods return one of three values: 
        1 (real hardware, initialization succeeded), 2 (simulated hardware), 3 (initialization failed / error)
            
            Returns - 2
        """
        logger.info("Abakus initialized")
        return 2
    
    @log_on_end(logging.INFO, "Abakus measurements started", logger=logger)
    def start_measurement(self):
        pass

    @log_on_end(logging.INFO, "Abakus measurements stopped", logger=logger)
    def stop_measurement(self):
        return 0

    # @log_on_end(logging.INFO, "Abakus queried", logger=logger)
    def query(self):
        """Returns - timestamp (float, epoch time), data_out (str, unprocessed string)"""

        fake_abakus_data = "00000008 00000000 00000009 00000000 00000010 00000000 00000011 00000000 00000012 00000000 00000013 00000000 00000014 00000000 00000016 00000000 00000018 00000000 00000020 00000000 00000022 00000000 00000024 00000000 00000026 00000000 00000028 00000000 00000030 00000000 00000032 00000000 00000034 00000000 00000037 00000000 00000040 00000000 00000043 00000000 00000046 00000000 00000049 00000000 00000052 00000000 00000055 00000000 00000058 00000000 00000062 00000000 00000066 00000000 00000070 00000000 00000075 00000000 00000080 00000000 00000090 00000000 00000100 00000000"
        timestamp = time.time()

        # If we're in debug mode, return this fake reading
        if debug:
            output = fake_abakus_data
        # Otherwise, return NAN
        else:
            output = "nan"

        return timestamp, output

class Picarro():
    def __init__(self, serial_port="COM3", baud_rate=19200) -> None:
        """Fake hardware, pretends to do everything the real Picarro class does"""
        self.initialize_pyserial(serial_port, baud_rate)

    def initialize_pyserial(self, port, baud):
        logger.info(f"Fake hardware, pretending to use serial port {port} with baud {baud}")

    
    @log_on_start(logging.INFO, "Initializing Picarro", logger=logger)
    def initialize_picarro(self):
        """
        The initialization methods return one of three values: 
        1 (real hardware, initialization succeeded), 2 (simulated hardware), 3 (initialization failed / error)
            
            Returns - 2
        """
        logger.info("Initialized Picarro")
        return 2

    # @log_on_end(logging.INFO, "Picarro queried", logger=logger)
    def query(self):
        """Returns - timestamp (float, epoch time), picarro_reading (str, raw data)"""
        fake_picarro_data = "2024-08-22 13:52:47.246;-0.990;-0.001;-0.006;0.021"
        timestamp = time.time()

        # Split along the semicolons
        fake_picarro_data = fake_picarro_data.split(";")

        # If we're in debug mode, return this fake reading
        if debug:
            output = fake_picarro_data
        # Otherwise, return NAN
        else:
            output = "nan"

        return timestamp, output

class FlowMeter():
    def __init__(self, serial_port="COM6", baud_rate=115200, sensor_type="SLI2000") -> None:
        """Fake hardware, pretends to do everything the real FlowMeter class does"""
        self.initialize_pyserial(serial_port, baud_rate)
        self.sensor_type = sensor_type

    def initialize_pyserial(self, port, baud):
        logger.info(f"Fake hardware, pretending to use serial port {port} with baud {baud}")

    @log_on_start(logging.INFO, "Initializing Flowmeter", logger=logger)
    def initialize_flowmeter(self):
        """
        The initialization methods return one of three values: 
        1 (real hardware, initialization succeeded), 2 (simulated hardware), 3 (initialization failed / error)
            
            Returns - 2
        """
        logger.info(f"Flowmeter {self.sensor_type} initialized")
        return 2
    
    def start_measurement(self):
        logger.info(f"Flowmeter {self.sensor_type} measurements started")

    @log_on_end(logging.INFO, "Flowmeter measurements stopped", logger=logger)
    def stop_measurement(self):
        pass

    # @log_on_end(logging.INFO, "Flowmeter queried", logger=logger)
    def query(self):
        """Returns - timestamp (float, epoch time), data_out ([int], raw data)"""
        timestamp = time.time()
        fake_flowmeter_sli2000_reading = [126, 0, 53, 0, 2, 255, 252, 205, 126]

        fake_flowmeter_sls1500_reading = [126, 0, 53, 0, 2, 255, 247, 210, 126]
                                    # [126, 0, 53, 0, 2, 255, 246, 211, 126] # also

        # If we're in debug mode, return this fake reading
        if debug:
            output = fake_flowmeter_sli2000_reading
        # Otherwise, return NAN
        else:
            output = "nan"

        return timestamp, output

class Dimetix():
    def __init__(self, serial_port="COM8", baud_rate=19200) -> None:
        """Fake hardware, pretends to do everything the real Dimetix laser class does"""
        self.initialize_pyserial(serial_port, baud_rate)

    def __del__(self) -> None:
        self.stop_laser()

    def initialize_pyserial(self, port, baud):
        logger.info(f"Fake hardware, pretending to use serial port {port} with baud {baud}")
    
    @log_on_start(logging.INFO, "Initializing Dimetix laser", logger=logger)
    def initialize_laser(self):
        """
        The initialization methods return one of three values: 
        1 (real hardware, initialization succeeded), 2 (simulated hardware), 3 (initialization failed / error)
            
            Returns - 2
        """
        logger.info("Laser initialized")
        return 2
    
    @log_on_end(logging.INFO, "Dimetix laser turned on", logger=logger)
    def start_laser(self):
        pass

    @log_on_end(logging.INFO, "Dimetix laser turned off", logger=logger)
    def stop_laser(self):
        return 0

    # @log_on_end(logging.INFO, "Dimetix laser queried distance", logger=logger)
    def query_distance(self):
        """Returns - timestamp (float, epoch time), fake_laser_distance_reading (str, unprocessed string)"""
        fake_laser_distance_reading = "g0g+00000101" # raw serial output "g0t-00000023"
        timestamp = time.time()

        # If we're in debug mode, return this fake reading
        if debug:
            output = fake_laser_distance_reading
        # Otherwise, return NAN
        else:
            output = "nan"

        return timestamp, output
    
    # @log_on_end(logging.INFO, "Dimetix laser queried temperature", logger=logger)
    def query_temperature(self):
        """Returns - timestamp (float, epoch time), fake_laser_temp_reading (str, unprocessed string)"""
        fake_laser_temp_reading = "g0t-00000023"
        timestamp = time.time()

        # If we're in debug mode, return this fake reading
        if debug:
            output = fake_laser_temp_reading
        # Otherwise, return NAN
        else:
            output = "nan"

        return timestamp, output

class Bronkhorst():
    def __init__(self, serial_port, baud_rate=38400) -> None:
        """Not yet done. Fake hardware, pretends to do everything the real melthead class does"""
        self.initialize_pyserial(serial_port, baud_rate)

    def initialize_pyserial(self, port, baud):
        logger.info(f"Fake hardware, pretending to use serial port {port} with baud {baud}")

    @log_on_start(logging.INFO, "Initializing Bronkhorst")
    def initialize_bronkhorst(self):
        """
        The initialization methods return one of three values: 
        1 (real hardware, initialization succeeded), 2 (simulated hardware), 3 (initialization failed / error)
            
            Returns - 2
        """
        logger.info("Bronkhorst initialized")
        return 2
    
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
        else:
            # if within some pressure bound:
                # do a thing
            valid_setpoint = True

        return valid_setpoint
    
    def send_setpoint(self, setpoint):
        setpoint_valid = self.validate_setpoint(setpoint)
        if setpoint_valid:
            logger.info(f"Set Bronkhorst setpoint to {setpoint} mbar")

    # @log_on_end(logging.INFO, "Bronkhorst queried", logger=logger)
    def query(self):
        """Returns - timestamp (float, epoch time), output ((bytestr, bytestr, bytestr), responses for fsetpoint, measure, and a
            chained response for fmeasure  & temperature)"""
        
        fsetpoint = ':0880022141453B8000\r\n'
        meas = ':06800201217D00\r\n'
        fmeas_and_temp = ':0E8002A1404479C0E0214741C80000'
        timestamp = time.time()

        # If we're in debug mode, return this fake reading
        if debug:
            output = (fsetpoint, meas, fmeas_and_temp)
        # Otherwise, return NAN
        else:
            output = "nan"
        
        return timestamp, output
    
class MeltHead:
    def __init__(self, serial_port, baud_rate=38400) -> None:
        """Fake hardware, pretends to do everything the real melthead does"""
        self.initialize_pyserial(serial_port, baud_rate)

    def initialize_pyserial(self, port, baud):
        pass

    @log_on_start(logging.INFO, "Initializing Melthead", logger=logger)
    def initialize_pid(self, timeout=10):
        """
        The initialization methods return one of three values: 
        1 (real hardware, initialization succeeded), 2 (simulated hardware), 3 (initialization failed / error)
            
            Returns - 2
        """
        logger.info("Melthead initialized")
        return 2
    
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
        else:
            if setpoint < 25:
                valid_setpoint = True

        return valid_setpoint

    @log_on_end(logging.INFO, "Started PID control loop", logger=logger)
    def start_control_loop(self):
        pass

    @log_on_end(logging.INFO, "Stopped PID control loop", logger=logger)
    def stop_control_loop(self):
        pass

    def send_setpoint(self, setpoint):
        setpoint_valid = self.validate_setpoint(setpoint)
        if setpoint_valid:
            logger.info(f"Set melthead setpoint to {setpoint} degC")


