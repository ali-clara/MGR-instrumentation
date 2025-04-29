# -------------
# The sensor class
# 
# Currently can't be run from here, since it's importing things from the sensor_interfaces package. Need to figure that out.
# -------------

# General imports
import serial
from serial import SerialException
import time
import yaml
import numpy as np
import pandas as pd
import datetime

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

# Custom imports
from main_pipeline.bus import Bus
from sensor_interfaces import sim_instruments

####### -------------------------------- Try to connect to all the sensors -------------------------------- #######
# If we can connect, use the real sensor at the specified serial port and baud. if not, use simulated hardware. 
# This allows us to have the entire process running even if we only want a few sensors online

# Load the sensor comms configuration file - dictionary with sensor serial ports and baud rates
try:
    with open("config/sensor_comms.yaml", 'r') as stream:
        comms_config = yaml.safe_load(stream)
except FileNotFoundError as e:
    logger.error(f"Error in loading the sensor_comms configuration file: {e} Check your file storage and directories")

# Picarro Gas
try:
    serial.Serial(port=comms_config["Picarro Gas"]["serial port"], baudrate=comms_config["Picarro Gas"]["baud rate"])
    from sensor_interfaces.picarro_interface import Picarro
    logger.info(f"Successfully connected to port {comms_config['Picarro Gas']['serial port']}, using real Picarro Gas hardware")
except SerialException:
    from sensor_interfaces.sim_instruments import Picarro
    logger.info(f"Couldn't find Picarro at port {comms_config['Picarro Gas']['serial port']}, shadowing sensor calls with substitute functions")
except KeyError as e:
    logger.warning(f"Key error in reading sensor_comms configuration file: {e}. Check that your dictionary keys match")

# Picarro Water
# try:
#     serial.Serial(port=comms_config["Picarro Water"]["serial port"], baudrate=comms_config["Picarro Water"]["baud rate"])
#     from sensor_interfaces.picarro_interface import Picarro
#     logger.info(f"Successfully connected to port {comms_config['Picarro Water']['serial port']}, using real Picarro Water hardware")
# except SerialException:
#     from sensor_interfaces.sim_instruments import Picarro
#     logger.info(f"Couldn't find Picarro at port {comms_config['Picarro Water']['serial port']}, shadowing sensor calls with substitute functions")
# except KeyError as e:
#     logger.warning(f"Key error in reading sensor_comms configuration file: {e}. Check that your dictionary keys match")

# Abakus 
try:
    serial.Serial(port=comms_config["Abakus Particle Counter"]["serial port"], baudrate=comms_config["Abakus Particle Counter"]["baud rate"])
    from sensor_interfaces.abakus_interface import Abakus
    logger.info(f"Successfully connected to port {comms_config['Abakus Particle Counter']['serial port']}, using real Abakus hardware")
except SerialException:
    from sensor_interfaces.sim_instruments import Abakus
    logger.warning(f"Couldn't find Abakus at port {comms_config['Abakus Particle Counter']['serial port']}, shadowing sensor calls with substitute functions")
except KeyError as e:
    logger.error(f"Key error in reading sensor_comms configuration file: {e}. Check that your dictionary keys match")

# Flowmeter - they both need to be plugged in to connect to either
try:
    serial.Serial(port=comms_config["Flowmeter SLI2000 (Green)"]["serial port"], baudrate=comms_config["Flowmeter SLI2000 (Green)"]["baud rate"])
    serial.Serial(port=comms_config["Flowmeter SLS1500 (Black)"]["serial port"], baudrate=comms_config["Flowmeter SLS1500 (Black)"]["baud rate"])
    from sensor_interfaces.flowmeter_interface import FlowMeter
    logger.info(f"Successfully connected to port {comms_config['Flowmeter SLI2000 (Green)']['serial port']} and " +
                f"{comms_config['Flowmeter SLS1500 (Black)']['serial port']}, using real Flowmeter hardware")
except SerialException:
    from sensor_interfaces.sim_instruments import FlowMeter
    logger.warning(f"Couldn't find Flowmeter at port {comms_config['Flowmeter SLI2000 (Green)']['serial port']} and " + 
                f"{comms_config['Flowmeter SLS1500 (Black)']['serial port']}, shadowing sensor calls with substitute functions")
except KeyError as e:
    logger.error(f"Key error in reading sensor_comms configuration file: {e}. Check that your dictionary keys match")

# Laser
try:
    serial.Serial(port=comms_config['Laser Distance Sensor']['serial port'], baudrate=comms_config["Laser Distance Sensor"]["baud rate"])
    from sensor_interfaces.laser_interface import Dimetix
    logger.info(f"Successfully connected to port {comms_config['Laser Distance Sensor']['serial port']}, using real Dimetix hardware")
except SerialException:
    from sensor_interfaces.sim_instruments import Dimetix
    logger.warning(f"Couldn't find Dimetix laser at port {comms_config['Laser Distance Sensor']['serial port']}, shadowing sensor calls with substitute functions")
except KeyError as e:
    logger.error(f"Key error in reading sensor_comms configuration file: {e}. Check that your dictionary keys match")

# Bronkhorst
try:
    serial.Serial(port=comms_config['Bronkhorst Pressure']['serial port'], baudrate=comms_config['Bronkhorst Pressure']['baud rate'])
    from sensor_interfaces.bronkhorst_interface import Bronkhorst
    logger.info(f"Successfully connected to port {comms_config['Bronkhorst Pressure']['serial port']}, using real Bronkhorst hardware")
except SerialException:
    from sensor_interfaces.sim_instruments import Bronkhorst
    logger.warning(f"Couldn't find Bronkhorst at port {comms_config['Bronkhorst Pressure']['serial port']}, shadowing sensor calls with substitute functions")
except KeyError as e:
    logger.error(f"Key error in reading sensor_comms configuration file: {e}. Check that your dictionary keys match")

# Melthead
try:
    serial.Serial(port=comms_config['Melthead']['serial port'], baudrate=comms_config['Melthead']['baud rate'])
    from sensor_interfaces.melthead_interface import MeltHead
    logger.info(f"Successfully connected to port {comms_config['Melthead']['serial port']}, using real Melthead hardware")
except SerialException:
    from sensor_interfaces.sim_instruments import MeltHead
    logger.warning(f"Couldn't find Melthead at port {comms_config['Melthead']['serial port']}, shadowing sensor calls with substitute functions")
except KeyError as e:
    logger.error(f"Key error in reading sensor_comms configuration file: {e}. Check that your dictionary keys match")

class Sensor():
    """Class that reads from the different sensors and publishes that data over busses"""
    @log_on_end(logging.INFO, "Sensor class initiated", logger=logger)
    def __init__(self, debug=False) -> None:
        # Initialize the sensors with the appropriate serial port and baud rate (set in config/sensor_comms.yaml, make sure the dictionary keys here match)
        self.abakus = Abakus(serial_port=comms_config["Abakus Particle Counter"]["serial port"], baud_rate=comms_config["Abakus Particle Counter"]["baud rate"])
        self.flowmeter_sli2000 = FlowMeter(sensor_type="sli2000", serial_port=comms_config["Flowmeter SLI2000 (Green)"]["serial port"], baud_rate=comms_config["Flowmeter SLI2000 (Green)"]["baud rate"])
        self.flowmeter_sls1500 = FlowMeter(sensor_type="sls1500", serial_port=comms_config["Flowmeter SLS1500 (Black)"]["serial port"], baud_rate=comms_config["Flowmeter SLS1500 (Black)"]["baud rate"])
        self.laser = Dimetix(serial_port=comms_config["Laser Distance Sensor"]["serial port"], baud_rate=comms_config["Laser Distance Sensor"]["baud rate"])
        self.gas_picarro = Picarro(serial_port=comms_config["Picarro Gas"]["serial port"], baud_rate=comms_config["Picarro Gas"]["baud rate"])
        # self.water_picarro = Picarro(serial_port=comms_config["Picarro Water"]["serial port"], baud_rate=comms_config["Picarro Water"]["baud rate"])
        self.bronkhorst = Bronkhorst(serial_port=comms_config["Bronkhorst Pressure"]["serial port"], baud_rate=comms_config["Bronkhorst Pressure"]["baud rate"])
        self.melthead = MeltHead(serial_port=comms_config["Melthead"]["serial port"], baud_rate=comms_config["Melthead"]["baud rate"])

        # Read in the sensor config file to grab a list of all the sensors we're working with
        try:
            with open("config/sensor_data.yaml", 'r') as stream:
                self.big_data_dict = yaml.safe_load(stream)
        except FileNotFoundError as e:
            logger.error(f"Error in loading the sensor data config file: {e}")
            self.big_data_dict = {}
        
        self.sensor_names = list(self.big_data_dict.keys())

        # Create a dictionary to store the status of each sensor (0: offline, 1: online, 2: disconnected/simulated)
        self.sensor_status_dict = {}
        for name in self.sensor_names:
            self.sensor_status_dict.update({name:0})

        # Sim instruments has a "debug" flag - if True, it will return fake readings so we can test plotting, saving, etc. If False,
        # it returns np.nan. It defaults to False so we don't accidentally save fake data as if it were real
        sim_instruments.setSimDebugMode(debug)

    def __del__(self) -> None:
        self.shutdown_sensors()

    @log_on_start(logging.INFO, "Initializing sensors", logger=logger)
    @log_on_end(logging.INFO, "Finished initializing sensors", logger=logger)
    def initialize_sensors(self):
        """
        Method to take each sensor through a sequence to check that it's on and getting valid readings.
        **If you're adding a new sensor, you probably need to modify this method**

        Returns - status of each sensor 
        """

        # Fill in the dictionary with the results of calling the sensor init functions
        self.sensor_status_dict["Abakus Particle Counter"] = self.abakus.initialize_abakus()
        self.sensor_status_dict["Picarro Gas"] = self.gas_picarro.initialize_picarro()
        # self.sensor_status_dict["Picarro Water"] = self.water_picarro.initialize_picarro()
        self.sensor_status_dict["Laser Distance Sensor"] = self.laser.initialize_laser()
        self.sensor_status_dict["Bronkhorst Pressure"] = self.bronkhorst.initialize_bronkhorst()
        self.sensor_status_dict["Melthead"] = self.melthead.initialize_pid()

        # The flowmeters are a little special, since it's two sensors in one - deal with that here
        # Initialize and grab the results of flowmeter initialization
        sli2000 = self.flowmeter_sli2000.initialize_flowmeter()
        sls1500 = self.flowmeter_sls1500.initialize_flowmeter()
        # If both flowmeters are initialized, return that we're initialized
        if sli2000 == 1 and sls1500 == 1:
            flowmeter_status = 1
        # If both flowmeters are simulated, return that we're simulated
        elif sli2000 == 2 and sls1500 == 2:
            flowmeter_status = 2
        # Per how I've set up sim and real flowmeter imports, they're either both sim or both real. So the only other options are
            # one initializes and one fails, or both fail. Either way, return fail. 
        else:
            flowmeter_status = 0

        self.sensor_status_dict["Flowmeter"] = flowmeter_status

        return self.sensor_status_dict

    @log_on_start(logging.INFO, "Shutting down sensors", logger=logger)
    @log_on_end(logging.INFO, "Finished shutting down sensors", logger=logger)
    def shutdown_sensors(self):
        """
        Method to stop measurements/exit data collection/turn off the sensors that need it; the rest don't have a shutdown feature.
        **If you're adding a new sensor, you probably need to modify this method.**
        
        Shuts down - Abakus particle counter, Laser distance sensor
        """
        # Updates the status dictionary with the results of shutting down the sensors
        self.sensor_status_dict["Abakus Particle Counter"] = self.abakus.stop_measurement()
        self.sensor_status_dict["Laser Distance Sensor"] = self.laser.stop_laser()

        return self.sensor_status_dict
    
    ## ------------------- ABAKUS PARTICLE COUNTER ------------------- ##
    def abakus_producer(self, abakus_bus:Bus):
        """Method that writes Abakus data to its bus"""
        data = self.read_abakus()
        abakus_bus.write(data)

    def read_abakus(self):
        """Method that gets data from the Abakus \n
            Returns - tuple (timestamp[float, epoch time], data_out[str, bins and counts])"""
        timestamp, data_out = self.abakus.query()
        return timestamp, data_out

    ## ------------------- FLOWMETER ------------------- ##
    def flowmeter_sli2000_producer(self, flowmeter_bus:Bus):
        """Method that writes flowmeter SLI2000 data to its bus"""
        data = self.read_flowmeter(flowmeter_model="SLI2000")
        flowmeter_bus.write(data)

    def flowmeter_sls1500_producer(self, flowmeter_bus:Bus):
        """Method that writes flowmeter SLS1500 data to its bus"""
        data = self.read_flowmeter(flowmeter_model="SLS1500")
        flowmeter_bus.write(data)

    def read_flowmeter(self, flowmeter_model):
        """
        Method that gets data from a flow meter, specified by the model number. 
        Querying is the same for both models, but processing is different.

            Returns - tuple (timestamp[float, epoch time], data_out([int], bytes)
        """
        samples_per_query = self.big_data_dict["Flowmeter"]["Other"]["Samples Per Query"]
        data_out = []
        if flowmeter_model == "SLI2000":
            for _ in range(samples_per_query):
                timestamp, reading = self.flowmeter_sli2000.query()
                data_out.append(reading)
        elif flowmeter_model == "SLS1500":
            for _ in range(samples_per_query):
                timestamp, reading = self.flowmeter_sls1500.query()
                data_out.append(reading)
        else:
            timestamp = 0.0
            data_out = [0]

        return timestamp, data_out
    
    # ------------------- DIMETIX LASER DISTANCE SENSOR ------------------- ##
    def laser_producer(self, laser_bus:Bus):
        """Method that writes laser data to its bus"""
        data = self.read_laser()
        laser_bus.write(data)

    def read_laser(self):
        """Method that gets data from the Dimetix laser

            Returns - tuple (timestamp [epoch time], data_out [str])"""
        timestamp, distance = self.laser.query_distance()
        timestamp, temp = self.laser.query_temperature()
        return timestamp, (distance, temp)
    
    ## ------------------- PICARRO ------------------- ##
    def picarro_gas_producer(self, picarro_bus:Bus):
        """Method that writes Picarro gas concentration data to its bus"""
        data = self.read_picarro("GAS")
        picarro_bus.write(data)

    def picarro_water_producer(self, picarro_bus:Bus):
        """Method that writes Picarro water isotope data to its bus"""
        data = self.read_picarro("WATER")
        picarro_bus.write(data)

    def read_picarro(self, picarro_model):
        """Method that gets data from a Picarro, specified by the model

            Returns - tuple (timestamp[float, epoch time], data_out[str])"""
        if picarro_model == "GAS":
            timestamp, data_out = self.gas_picarro.query()
        elif picarro_model == "WATER":
            timestamp, data_out = self.water_picarro.query()
        else:
            timestamp = [0.0]
            data_out = ["0"]
        return timestamp, data_out

    ## ------------------- BRONKHORST PRESSURE SENSOR ------------------- ##
    def bronkhorst_producer(self, bronkhorst_bus:Bus):
        """Method that writes bronkhorst data to its bus"""
        data = self.read_bronkhorst()
        bronkhorst_bus.write(data)

    def read_bronkhorst(self):
        """Method that gets data from the Bronkhorst pressure sensor

            Returns - tuple (timestamp [epoch time], data_out [(bytestr, bytestr)])"""
        timestamp, data_out = self.bronkhorst.query()
        return timestamp, data_out
    