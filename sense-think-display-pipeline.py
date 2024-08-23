import numpy as np
import time
import concurrent.futures
from readerwriterlock import rwlock

import serial
from serial import SerialException
import pandas as pd
import keyboard

import logging
from logdecorator import log_on_start , log_on_end , log_on_error

logging_format = "%(asctime)s: %(message)s"
logging.basicConfig(format=logging_format, level=logging.INFO, datefmt ="%H:%M:%S")
logging.getLogger().setLevel(logging.DEBUG)


# Imports sensor classes for either real hardware or shadow hardware, depending on the situation
test_port = "COM3"
test_baud = 15200
try:
    serial.Serial(port=test_port, baudrate=test_baud, timeout=5) # CHECKS IF WE'RE CONNECTED TO HARDWARE, REPLACE W SOMETHING BETTER
    from sensor_interfaces.abakus_interface import Abakus
    from sensor_interfaces.flowmeter_interface import FlowMeter
    from sensor_interfaces.laser_interface import Dimetix
    logging.info(f"Successfully connected to port {test_port}, using real hardware")
except:
    from sim_instruments import Abakus, FlowMeter, Dimetix
    logging.info(f"Couldn't find real hardware at port {test_port}, shadowing sensor calls with substitute functions")

class Bus():
    """Class that sets up a bus to pass information around with read/write locking"""
    def __init__(self):
        self.message = None
        self.lock = rwlock.RWLockWriteD() # sets up a lock to prevent simultanous reading and writing

    def write(self, message):
        with self.lock.gen_wlock():
            self.message = message

    def read(self):
        with self.lock.gen_rlock():
            message = self.message
        return message
    
class Sensor():
    """Class that reads from the different sensors and publishes that data over busses"""
    def __init__(self) -> None:
        ### SHOULD EITHER READ IN OR BE PASSED IN A .YAML FILE HERE THAT SPECIFIES PORTS AND BAUDS ###
        self.abakus = Abakus()
        self.flowmeter_sli2000 = FlowMeter(serial_port="COM6")
        self.flowmeter_sls1500 = FlowMeter(serial_port="COM7")
        self.laser = Dimetix()

    def abakus_producer(self, abakus_bus:Bus, delay):
        """Method that writes Abakus data to its bus"""
        data = self.read_abakus()
        abakus_bus.write(data)
        time.sleep(delay)

    def read_abakus(self):
        """Method that gets data from the Abakus class\n
            Returns - tuple (timestamp[float, epoch time], data_out[str, bins and counts])"""
        timestamp, data_out = self.abakus.query()
        return timestamp, data_out

    def flowmeter_sli2000_producer(self, flowmeter_bus:Bus, delay):
        """Method that writes Flowmeter data to its bus"""
        data = self.read_flowmeter(flowmeter_model="SLI2000")
        flowmeter_bus.write(data)
        time.sleep(delay)

    def flowmeter_sls1500_producer(self, flowmeter_bus:Bus, delay):
        data = self.read_flowmeter(flowmeter_model="SLS1500")
        flowmeter_bus.write(data)
        time.sleep(delay)

    def read_flowmeter(self, flowmeter_model):
        """
        Method that gets data from the FlowMeter class specified by the model number. 
        Querying is the same for both models, but processing is different.

            Returns - tuple (timestamp[float, epoch time], data_out([int], bytes)
        """
        if flowmeter_model == "SLI2000":
            timestamp, data_out = self.flowmeter_sli2000.query()
        elif flowmeter_model == "SLS1500":
            timestamp, data_out = self.flowmeter_sls1500.query()
        else:
            timestamp = 0.0
            data_out = [0]
        
        return timestamp, data_out
    
    def laser_producer(self, laser_bus:Bus, delay):
        data = self.read_laser()
        laser_bus.write(data)
        time.sleep(delay)

    def read_laser(self):
        """Method that gets data from the Laser class. 
            Returns - tuple (timestamp [epoch time], data_out [str])"""
        timestamp, data_out = self.laser.query_distance()
        return timestamp, data_out

class Interpretor():
    """Class that reads data from each sensor bus, does some processing, and republishes on an interpretor bus."""
    def __init__(self) -> None:
        # Set all initial measurements to 0, with the correct formatting to be updated by the sensor outputs
        self.abakus_bin_num = 32
        init_abakus_data = {"time (epoch)": [0.0]*self.abakus_bin_num, "bins": [0]*self.abakus_bin_num, "counts": [0]*self.abakus_bin_num}
        self.abakus_data = pd.DataFrame(init_abakus_data)
        self.abakus_total_counts = pd.DataFrame({"time (epoch)": [0.0], "total counts": 0})

        self.flowmeter_sli2000_data = pd.DataFrame({"time (epoch)": [0.0], "flow (uL/min)": [0.0]})
        self.flowmeter_sls1500_data = pd.DataFrame({"time (epoch)": [0.0], "flow (mL/min)": [0.0]})

        init_laser_data = {"time (epoch)": [0.0], "distance (cm)": [0.0], "temperature (°C)": [99.99]}
        self.laser_data = pd.DataFrame(init_laser_data)

    def main_consumer_producer(self, abakus_bus:Bus, flowmeter_sli_bus:Bus, flowmeter_sls_bus:Bus, laser_bus:Bus,
                               output_bus:Bus, delay):
        """Method to read from all the sensor busses and write one compiled output file"""
        # Read from all the busses
        abakus_timestamp, abakus_data = abakus_bus.read()
        flowmeter_sli_timestamp, flowmeter_sli_data = flowmeter_sli_bus.read()
        flowmeter_sls_timestamp, flowmeter_sls_data = flowmeter_sls_bus.read()
        laser_timestamp, laser_data = laser_bus.read()

        # Process the raw data from each bus (each produces a data frame)
        self.process_abakus_data(abakus_timestamp, abakus_data)
        self.process_flowmeter_data(flowmeter_sli_timestamp, flowmeter_sli_data, model="SLI2000", scale_factor=5, units="uL/min")
        self.process_flowmeter_data(flowmeter_sls_timestamp, flowmeter_sls_data, model="SLS1500", scale_factor=500, units="mL/min")
        self.process_laser_data(laser_timestamp, laser_data)
        
        # Concatanate the data frames and take a look at the differece between their timestamps
        big_df = pd.concat([self.abakus_total_counts, self.flowmeter_sli2000_data, 
                            self.flowmeter_sls1500_data, self.laser_data], axis=1)
        # big_df["time_difference"] = [abakus_timestamp - flowmeter_sli_timestamp]
        print(f"time difference 1: {abakus_timestamp - flowmeter_sli_timestamp}")
        print(f"time difference 2: {abakus_timestamp - flowmeter_sls_timestamp}")
        print(f"time difference 3: {abakus_timestamp - laser_timestamp}")
        
        # Write to the output bus
        output_bus.write(big_df)
        time.sleep(delay)

    ## ------------------- ABAKUS PARTICLE COUNTER ------------------- ##
    def abakus_consumer_producer(self, abakus_bus:Bus, particle_count_bus:Bus, delay):
        timestamp, data_out = abakus_bus.read()
        self.process_abakus_data(timestamp, data_out)
        particle_count_bus.write(self.abakus_data)
        time.sleep(delay)
        
    def process_abakus_data(self, timestamp, data_out:str):
        """
        Function to processes the data from querying the Abakus. The first measurement comes through with 
        more than the expected 32 channels (since the Abakus holds onto the last measurement from the last batch)
        so you should query the Abakus a couple times before starting data processing. We have a check for that here
        just in case.

            Updates - self.abakus_data (pd.df, processed timestamp, bins, and particle count/bin)
        """
        # Data processing - from Abby's stuff originally
        output = data_out.split() # split into a list
        bins = [int(i) for i in output[::2]] # grab every other element, starting at 0, and make it an integer while we're at it
        counts = [int(i) for i in output[1::2]] # grab every other element, starting at 1, and make it an integer

        # If we've recieved the correct number of bins, update the measurement. Otherwise, log an error
        if len(bins) == self.abakus_bin_num: 
            logging.info("Abakus data good, recieved 32 channels.")
            self.abakus_data["time (epoch)"] = timestamp
            self.abakus_data["bins"] = bins
            self.abakus_data["counts"] = counts
            self.abakus_total_counts["time (epoch)"] = timestamp
            self.abakus_total_counts["total counts"] = np.sum(counts)
        else:
            logging.debug(f"Recieved {len(output)} Abakus channels instead of the expected 32. Not updating measurement")
            
    ## ------------------- FLOWMETER ------------------- ##
    def flowmeter_sli2000_consumer_producer(self, flowmeter_bus:Bus, fluid_flow_bus:Bus, delay):
        timestamp, data_out = flowmeter_bus.read()
        self.process_flowmeter_data(timestamp, data_out, model="SLI2000", scale_factor=5, units="uL/min")
        fluid_flow_bus.write(self.flowmeter_sli2000_data)
        time.sleep(delay)

    def flowmeter_sls1500_consumer_producer(self, flowmeter_bus:Bus, fluid_flow_bus:Bus, delay):
        timestamp, data_out = flowmeter_bus.read()
        self.process_flowmeter_data(timestamp, data_out, model="SLS1500", scale_factor=500, units="mL/min")
        fluid_flow_bus.write(self.flowmeter_sls1500_data)
        time.sleep(delay)

    def process_flowmeter_data(self, timestamp, raw_data, model, scale_factor, units):
        """Method to process data from querying the Flowmeter. The scale factor and unit output of the two 
        models differs (SLI2000 - uL/min, SLS1500 - mL/min). Could make that the same if needed, but for now
        I want it to be consistent with the out-of-box software
        
            Updates - self.flowmeter_SLXXXXX_data (pd.df, processed timestamp and flow rate)"""
        # Check if reading is good
        validated_data = self.check_flowmeter_data(raw_data, model)
        # If it's good, try processing it
        try:
            if validated_data:
                rxdata = validated_data[4]
                ticks = self.twos_comp(rxdata[0])
                flow_rate = ticks / scale_factor

                if model == "SLI2000":
                    self.flowmeter_sli2000_data["time (epoch)"] = timestamp
                    self.flowmeter_sli2000_data[f"flow ({units})"] = flow_rate
                elif model == "SLS1500":
                    self.flowmeter_sls1500_data["time (epoch)"] = timestamp
                    self.flowmeter_sls1500_data[f"flow ({units})"] = flow_rate
                else:
                    logging.debug("Invalid flowmeter model given. Not updating measurement")
        # If that didn't work, give up this measurement
        except Exception as e:
            logging.debug(f"Encountered exception in processing flowmeter {model}: {e}. Not updating measurement.")

    def check_flowmeter_data(self, raw_data, model):
        """Method to validate the flowmeter data with a checksum and some other things. From Abby, I should
        check in with her about specifics. 

            Returns - a bunch of bytes if the data is valid, False if not"""
        try:
            adr = raw_data[1]
            cmd = raw_data[2]
            state = raw_data[3]
            if state != 0:
                raise Exception("Bad reply from flow meter")
            length = raw_data[4]
            rxdata8 = raw_data[5:5 + length]
            chkRx = raw_data[5 + length]

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
                    rxdata16.append(self.bytepack(rxdata8[i], rxdata8[i + 1]))  # convert to a 16-bit integer w/ little-endian byte order
                    i = i + 2  # +2 for pairs of bytes

            return adr, cmd, state, length, rxdata16, chkRx

        except Exception as e:
            logging.debug(f"Encountered exception in validating flowmeter {model}: {e}. Not updating measurement.")
            return False
    
    def bytepack(self, byte1, byte2):
        """ 
        Helper method to concatenate two uint8 bytes to uint16. Takes two's complement if negative
            Inputs - byte1 (uint8 byte), byte2 (uint8 byte)
            Return - binary16 (combined uint16 byte)
        """
        binary16 = (byte1 << 8) | byte2
        return binary16
    
    def twos_comp(self, binary):
        """Helper method to take two's complement of binary input if negative, returns input otherwise"""
        if (binary & (1 << 15)):
            n = -((binary ^ 0xFFFF) + 1)
        else:
            n = binary
        return n
    
    # ------------------- DIMETIX LASER DISTANCE SENSOR ------------------- ##
    def laser_consumer_producer(self, laser_bus:Bus, laser_distance_bus:Bus, delay):
        timestamp, data_out = laser_bus.read()

    def process_laser_data(self, timestamp, data_out):
        """
        Method to process data from querying the laser. It doesn't always like to return a valid result, but
        if it does, it's just the value in meters (I think, should check with Abby about getting the data sheet there) \n
        
            Updates - self.laser_data (pd.df, processed_timestamp, distance reading (cm)). 
            Doesn't currently have temperature because I was getting one or the other, and prioritized distance
        """
        try:
            output_cm = float(data_out) / 100
            self.laser_data["time (epoch)"] = timestamp
            self.laser_data["distance (cm)"] = output_cm
        except ValueError as e:
            logging.error(f"Error in converting distance reading to float: {e}. Not updating measurement")

    ## ------------------- PICARRO ------------------- ##
    
class Display():
    """Class that reads the interpreted data and displays it. Will eventually be on the GUI, for now it 
    reads the interpretor bus and prints the data"""
    def __init__(self) -> None:
        pass

    def display_consumer(self, interpretor_bus:Bus, delay):
        interp_data = interpretor_bus.read()
        logging.info(f"Data: \n{interp_data}")
        time.sleep(delay)

class Executor():
    """Class that handles passing the data around on all the busses. Still needs a clean shutdown."""
    def __init__(self) -> None:
        # Initialize the classes
        self.sensor = Sensor()
        self.interpretor = Interpretor()
        self.display = Display()

        # Initialize the busses
        self.abakus_bus = Bus()
        self.flowmeter_sli2000_bus = Bus()
        self.flowmeter_sls1500_bus = Bus()
        self.laser_bus = Bus()

        self.main_interp_bus = Bus()

        # Set the delay times (sec)
        self.sensor_delay = 0.1
        self.interp_delay = 0.1
        self.display_delay = 0.1
        
    def execute(self):
        """Method to execute the sensor, interpretor, and display classes with threading. Calls the appropriate methods within
        those classes and passes them the correct busses and delay times."""
        while not keyboard.is_pressed("q"):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                eAbakus = executor.submit(self.sensor.abakus_producer, self.abakus_bus, self.sensor_delay)
                eFlowMeterSLI2000 = executor.submit(self.sensor.flowmeter_sli2000_producer, self.flowmeter_sli2000_bus, self.sensor_delay)
                eFlowMeterSLS1500 = executor.submit(self.sensor.flowmeter_sls1500_producer, self.flowmeter_sls1500_bus, self.sensor_delay)
                eLaser = executor.submit(self.sensor.laser_producer, self.laser_bus, self.sensor_delay)
                
                eInterpretor = executor.submit(self.interpretor.main_consumer_producer, self.abakus_bus, self.flowmeter_sli2000_bus,
                                               self.flowmeter_sls1500_bus, self.laser_bus, self.main_interp_bus, self.interp_delay)

                eDisplay = executor.submit(self.display.display_consumer, self.main_interp_bus, self.display_delay)

            eAbakus.result()
            eFlowMeterSLI2000.result()
            eFlowMeterSLS1500.result()
            eLaser.result()
            eInterpretor.result()
            eDisplay.result()

if __name__ == "__main__":
    my_executor = Executor()
    my_executor.execute()