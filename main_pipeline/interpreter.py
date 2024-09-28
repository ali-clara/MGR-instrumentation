# -------------
# The interpreter class
# -------------

import numpy as np
import time
import yaml
import copy

try:
    from main_pipeline.bus import Bus
except ImportError:
    from bus import Bus

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

class Interpreter():
    """Class that reads data from each sensor bus, does some processing, and republishes on an Interpreter bus."""
    @log_on_end(logging.INFO, "Interpreter class initiated", logger=logger)
    def __init__(self) -> None:

       self._initialize_data_storage()

    def _initialize_data_storage(self):
        """Method to set up the dict for all sensors, with initial measurements zeroed and the correct formatting to be 
        updated by the sensor outputs. Does this by reading in the data buffer stored in config/sensor_data.yaml and 
        initializing all data values to NAN.
        """
        # Read in the sensor data config file to initialize the data buffer. 
        try:
            with open("config/sensor_data.yaml", 'r') as stream:
                self.big_data = yaml.safe_load(stream)
        except FileNotFoundError as e:
            logger.error(f"Error in loading the sensor data config file: {e}")
            self.big_data = {}

        t_i = time.time()
        self.channels = []
        # Comb through the keys, set the timestamp to the current time and the data to np.nan
        self.sensor_names = self.big_data.keys()
        for name in self.sensor_names:
            self.big_data[name]["Time (epoch)"] = t_i
            channels = list(self.big_data[name]["Data"].keys())
            for channel in channels:
                self.big_data[name]["Data"][channel] = np.nan
                self.channels.append(f"{name} {channel}")

    
    def main_consumer_producer(self, abakus_bus:Bus, flowmeter_sli_bus:Bus, flowmeter_sls_bus:Bus, laser_bus:Bus,
                               picarro_gas_bus:Bus, bronkhorst_bus:Bus, output_bus:Bus):
        """Method to read from all the sensor busses, process the data it reads, and write one compiled output file. 
        **If you add new sensors, you'll need to modify this method**

        Args:
            abakus_bus (Bus): 
            flowmeter_sli_bus (Bus): 
            flowmeter_sls_bus (Bus): 
            laser_bus (Bus): 
            picarro_gas_bus (Bus): 
            bronkhorst_bus (Bus): 
            output_bus (Bus): 
        """

        # Read from all the busses (should be in the form (timestamp, sensor_data))
        abakus_output = abakus_bus.read()
        flowmeter_sli_output = flowmeter_sli_bus.read()
        flowmeter_sls_output = flowmeter_sls_bus.read()
        laser_output = laser_bus.read()
        picarro_gas_output = picarro_gas_bus.read()
        # picarro_water_timestamp, picarro_water_data = picarro_water_bus.read()
        bronkhorst_output = bronkhorst_bus.read()

        # Process the raw data from each bus (saves the data in self.big_data)
        self.process_abakus_data(abakus_output)
        self.process_flowmeter_data(flowmeter_sli_output, model="SLI2000", scale_factor=5, units="uL/min")
        self.process_flowmeter_data(flowmeter_sls_output, model="SLS1500", scale_factor=500, units="mL/min")
        self.process_laser_data(laser_output)
        self.process_picarro_data(picarro_gas_output, model="GAS")
        # self.process_picarro_data(picarro_water_timestamp, picarro_water_data, model="WATER")
        self.process_bronkhorst_data(bronkhorst_output)
        
        # Uncomment these lines to check the difference in timestamps between the sensors
        # print(f"time difference 1: {self.big_data["Abakus Particle Counter"]["Time (epoch)"] - self.big_data["Picarro Gas"]["Time (epoch)"]}")
        # print(f"time difference 2: {self.big_data["Abakus Particle Counter"]["Time (epoch)"] - self.big_data["Laser Distance Sensor"]["Time (epoch)"]}")
        # print(f"time difference 3: {self.big_data["Abakus Particle Counter"]["Time (epoch)"] - self.big_data["Flowmeter"]["Time (epoch)"]}")
        # # print(f"time difference 4: {self.big_data["Abakus Particle Counter"]["Time (epoch)"] - self.big_data["Picarro Water"]["Time (epoch)"]}")
        
        # Write to the output bus
        output_bus.write(copy.deepcopy(self.big_data))

        # # Reset the dictionary to make sure we're not holding onto anything from the last data collection round
        for name in self.sensor_names:
            channels = list(self.big_data[name]["Data"].keys())
            for channel in channels:
                self.big_data[name]["Data"][channel] = np.nan


    ## ------------------- ABAKUS PARTICLE COUNTER ------------------- ##
    def process_abakus_data(self, abakus_data):
        """Function to processes the data from querying the Abakus and save it to the big data dictionary. 
        The first measurement comes through with more than the expected 32 channels (since the Abakus holds 
        onto the last measurement from the last batch) so you should query the Abakus a couple times before 
        starting data processing. We have a check for that here just in case.        

        Args:
            abakus_data (tuple): Data (timestamp, raw_data) read from the Abakus bus
        """
        # Try to split up the data into the readings we expect
        try:
            timestamp, data_out = abakus_data
        # If that didn't work, log it
        except TypeError as e:
            logger.warning(f"Error in extracting time and data from Abakus reading: {e}. Probably not a tuple. Not updating measurement")          
        # If it did work, process the data
        else:
            # If we're running shadow hardware and not in debug mode, the sensors return "nan". Check for that first
            if data_out == "nan":
                self.big_data["Abakus Particle Counter"]["Time (epoch)"] = timestamp
                return
            try:
                output = data_out.split() # split into a list
                bins = [int(i) for i in output[::2]] # grab every other element, starting at 0, and make it an integer while we're at it
                counts = [int(i) for i in output[1::2]] # grab every other element, starting at 1, and make it an integer
                total_counts = int(np.sum(counts))
                
                # If we've received the correct number of bins, update the measurement. Otherwise, log an error
                abakus_bin_num = 32
                if len(bins) == abakus_bin_num: 
                    self.big_data["Abakus Particle Counter"]["Time (epoch)"] = timestamp
                    self.big_data["Abakus Particle Counter"]["Other"]["Bins"] = bins
                    self.big_data["Abakus Particle Counter"]["Other"]["Counts/Bin"] = counts
                    self.big_data["Abakus Particle Counter"]["Data"]["Total Counts"] = total_counts
                else:
                    logger.warning("Didn't receive the expected 32 Abakus channels. Not updating measurement")
            except KeyError as e:
                logger.warning(f"Error in saving Abakus data to big dictionary: No key {e}. Not updating measurement")
            except Exception as e:
                logger.warning(f"Unexpected exception in processing abakus data: {e}. Not updating measurement.")
            
    ## ------------------- FLOWMETER ------------------- ##
    def process_flowmeter_data(self, flowmeter_data, model, scale_factor, units):
        """Method to process data from querying the Flowmeter. The scale factor and unit output of the two 
        models differs (SLI2000 - uL/min, SLS1500 - mL/min). Could make that the same if needed, but for now
        I want it to be consistent with the out-of-box software

        Args:
            flowmeter_data (tuple): tuple of (timestamp [float], data_out [list of n samples, where n is set in sensor_data.yaml])
            model (str): Flowmeter model (SLI2000 or SLS1500)
            scale_factor (int): Flowmeter scale factor, unique to device
            units (str): Data units (uL/min or mL/min)
        """
        # Try to split up the data into the readings we expect
        try:
            timestamp, data_out = flowmeter_data
        # If that didn't work, log it
        except TypeError as e:
            logger.warning(f"Error in extracting time and data from flowmeter {model} reading: {e}. Probably not a tuple. Not updating measurement")
        # If it did work, process the data
        else:
            # First, save the timestamp to the data dictionary 
            try:
                self.big_data["Flowmeter"]["Time (epoch)"] = timestamp
            # If we can't do that, something has gone wrong with our dictionary keys
            except KeyError as e:
                logger.warning(f"Error in saving flowmeter {model} timestamp to big dictionary. No key {e}.")
            # If we saved the timestamp OK, move on to processing the data
            else:
                # If we're running shadow hardware and not in debug mode, the sensors return "nan". Check for that first
                if data_out == "nan":
                    return
                # If we're not running shadow hardware, the flowmeter data is a list of n samples of flowmeter data.
                # For each one of those samples...
                flow_rates = []
                for sample in data_out:
                    # Check if the reading is good
                    validated_data = self.check_flowmeter_data(sample, model)
                    # If it's good, try processing it
                    if validated_data:
                        try:
                            rxdata = validated_data[4]
                            ticks = self.twos_comp(rxdata[0])
                            flow_rate = ticks / scale_factor
                        # If that didn't work, give up this measurement
                        except KeyError as e:
                            logger.warning(f"Error in saving flowmeter {model} data to big dictionary: No key {e}. Not updating measurement")
                        except Exception as e:
                            logger.warning(f"Unexpected exception in processing flowmeter {model}: {e}. Not updating measurement.")
                        # If that did work, append it to our running list of flow rates
                        else:
                            flow_rates.append(flow_rate)
                    # If it's bad, don't update the data
                    else:
                        flow_rates.append(np.nan)
                if np.nan in flow_rates:
                    # Take the average of our list (make it a nanmean in case any of the elements came through wrong)
                    averaged_flow_rate = np.nanmean(flow_rates)
                else:
                    averaged_flow_rate = np.mean(flow_rates)
                # Save the averaged list to our big data dictionary
                self.big_data["Flowmeter"]["Data"][f"{model} ({units})"] = averaged_flow_rate

    def check_flowmeter_data(self, flowmeter_data, model):
        """Method to validate the flowmeter data with a checksum and some other things. From Abby, I should
        check in with her about specifics. 

        Args:
            flowmeter_data (list): Raw data read from flowmeter. List of ints
            model (str): Flowmeter model (SLI2000 or SLS1500)

        Raises:
            Exception: Bad reply from flowmeter - if the third bit is nonzero (see docs)
            Exception: Bad checksum - (see docs)

        Returns:
            _type_: A string of bytes if it passes validation, False if not
        """
        try:
            # Check if the third bit indicates a bad reply or not
            raw_data = flowmeter_data
            adr = raw_data[1]
            cmd = raw_data[2]
            state = raw_data[3]
            if state != 0:
                raise Exception("Bad reply from flow meter")
            # Check checksum
            length = raw_data[4]
            rxdata8 = raw_data[5:5 + length]
            chkRx = raw_data[5 + length]
            chk = hex(adr + cmd + length + sum(rxdata8))  # convert integer to hexadecimal
            chk = chk[-2:]  # extract the last two characters of the string
            chk = int(chk, 16)  # convert back to an integer base 16 (hexadecimal)
            chk = chk ^ 0xFF  # binary check
            if chkRx != chk:
                raise Exception("Bad checksum")
        except Exception as e:
            logger.warning(f"Encountered exception in validating flowmeter {model}: {e}. Not updating measurement.")
            return False
        else:
            # If we passed those checks, compile valid output
            rxdata16 = []
            if length > 1:
                i = 0
                while i < length:
                    rxdata16.append(self.bytepack(rxdata8[i], rxdata8[i + 1]))  # convert to a 16-bit integer w/ little-endian byte order
                    i = i + 2  # +2 for pairs of bytes

            return adr, cmd, state, length, rxdata16, chkRx

    
    def bytepack(self, byte1, byte2):
        """Helper method to concatenate two uint8 bytes to uint16. Takes two's complement if negative

        Args:
            byte1 (uint8 byte): one byte
            byte2 (uint8 byte): a second byte

        Returns:
            binary16 (uint16 byte): Combined byte
        """
        binary16 = (byte1 << 8) | byte2
        return binary16
    
    def twos_comp(self, binary):
        """Helper method to take two's complement of binary input if negative, returns input otherwise
        
        Args:
            binary (uint16 byte): Binary input

        Returns:
            n (uint16 byte): Binary output
        """
        if (binary & (1 << 15)):
            n = -((binary ^ 0xFFFF) + 1)
        else:
            n = binary
        return n
    
    ## ------------------- DIMETIX LASER DISTANCE SENSOR ------------------- ##
    def process_laser_data(self, laser_data):
        """Method to process data from querying the laser. It doesn't always like to return a valid result, but
        if it does, it's just the value in meters (I think, should check with Abby about getting the data sheet there) \n
        
        Args:
            laser_data (tuple): Data (timestamp, raw_data) read from laser bus
        """
        # Try to split up the data into the readings we expect
        try:
            timestamp, data_out = laser_data
            distance, temp = data_out
        # If that didn't work, log it
        except TypeError as e:
            logger.warning(f"Error in extracting time and data from laser reading: {e}. Probably not a tuple. Not updating measurement")
        # If it did work, process the data
        else:
            
            # If we're running shadow hardware and not in debug mode, the sensors return "nan". Check for that first
            if distance == "nan" and temp == "nan":
                self.big_data["Laser Distance Sensor"]["Time (epoch)"] = timestamp
                return
            # Process distance
            try:
                # Make sure we always update the timestamp, even if we encounter an error later in processing
                self.big_data["Laser Distance Sensor"]["Time (epoch)"] = timestamp
                # The laser starts error messages as "g0@Eaaa", where "aaa" is the error code. If we get that, we've errored
                if distance[0:4] == "g0@E":
                    logger.warning(f"Recieved error message from laser distance: {distance} Check manual for error code. Not updating measurement")
                # Otherwise, the laser returns a successful distance reading as "g0g+aaaaaaaa", where "+a" is the dist in 0.1mm.
                # We need to slice away the first three characters, strip whitespace, and divide by 100 to get distance in cm
                else:
                    distance = distance[3:].strip()
                    distance_cm = float(distance) / 100.0
                    self.big_data["Laser Distance Sensor"]["Data"]["Distance (cm)"] = distance_cm
            except ValueError as e:
                logger.warning(f"Error in converting distance reading to float: {e}. Not updating measurement")
            except KeyError as e:
                logger.warning(f"Error in saving laser distance to big dictionary: No key {e}. Not updating measurement")
            except Exception as e:
                logger.warning(f"Unexpected exception in processing laser distance: {e}. Not updating measurement")

            # Process temperature
            try:
                # The laser starts error messages as "g0@Eaaa", where "aaa" is the error code. If we get that, we've errored
                if temp[0:4] == "g0@E":
                    logger.warning(f"Recieved error message from laser temperature: {temp}. Check manual for error code. Not updating measurement")
                # Otherwise, the laser returns successful temperature as "g0t±aaaaaaaa", where "±a" is the temp in 0.1°C.
                # We need to slice away the first three characters, strip whitespace, and divide by 10 to get distance in °C
                else:
                    temp = temp[3:].strip()
                    temp_c = float(temp) / 10.0
                    self.big_data["Laser Distance Sensor"]["Time (epoch)"] = timestamp
                    self.big_data["Laser Distance Sensor"]["Data"]["Temperature (C)"] = temp_c
            except ValueError as e:
                logger.warning(f"Error in converting temperature reading to float: {e}. Not updating measurement")
            except KeyError as e:
                logger.warning(f"Error in saving laser temperature to big dictionary: No key {e}. Not updating measurement")
            except Exception as e:
                logger.warning(f"Unexpected exception in processing laser temperature: {e}. Not updating measurement")

    ## ------------------- PICARRO ------------------- ##
    def process_picarro_data(self, picarro_data, model):
        """Method to process data from querying the picarro
        
        Args:
            picarro_data (tuple): Data (timestamp, raw_data) read from picarro bus
            model (str): Picarro model ("GAS" or "WATER")
        """
        if model == "GAS":
            # Try to split up the data into the readings we expect
            try:
                timestamp, data_out = picarro_data
            # If that failed, log it
            except TypeError as e:
                logger.warning(f"Error in extracting time and data from picarro reading: {e}. Probably not a tuple. Not updating measurement")
            # If it succeeded, process the data
            else:
                if data_out == "nan":
                    self.big_data["Picarro Gas"]["Time (epoch)"] = timestamp
                    return
                try:
                    # data_out[0] # the time at which the measurement was sampled, probably different than timestamp because
                    # the computer clocks drift
                    self.big_data["Picarro Gas"]["Time (epoch)"] = timestamp
                    self.big_data["Picarro Gas"]["Data"]["CO2"] = float(data_out[1])
                    self.big_data["Picarro Gas"]["Data"]["CH4"] = float(data_out[2])
                    self.big_data["Picarro Gas"]["Data"]["CO"] = float(data_out[3])
                    self.big_data["Picarro Gas"]["Data"]["H2O"] = float(data_out[4])
                except KeyError as e:
                    logger.warning(f"Encountered exception in processing picarro {model}: No key {e}. Not updating measurement.")
                except Exception as e:
                    logger.warning(f"Unexpected exception in processing picarro {model} data: {e}. Not updating measurement")
        elif model == "WATER":
            try:
                timestamp, data_out = picarro_data
            except Exception as e:
                logger.warning(f"Encountered exception in processing picarro {model}: {e}. Not updating measurement.")

    ## ------------------- BRONKHORST PRESSURE SENSOR ------------------- ##
    def process_bronkhorst_data(self, bronkhorst_data):
        """Method to process Bronkhorst output when querying setpoint/measurement and fmeasure/temperature
        
        Args:
            bronkhorst_data (tuple): Data (timestamp, data) read from bronkhorst bus"""
    

        # Try to split up the data into the readings we expect
        try:
            timestamp, (fsetpoint, meas, fmeas_and_temp) = bronkhorst_data
        # If that didn't work, log it
        except KeyError as e:
            logger.warning(f"Error in extracting time and data from bronkhorst reading: {e}. Probably not a tuple. Not updating measurement")
        # If it did work, parse the data
        else:
            if fsetpoint == "nan":
                self.big_data["Bronkhorst Pressure"]["Time (epoch)"] = timestamp
                return
            try:
                # Parsing measurement is straightforward - 
                # First, slice the setpoint and measurement out of the chained response and convert the hex string to an integer
                measure = int(meas[11:15], 16)
                # Then, scale the raw output (an int between 0-32000) to the measurement signal (0-100%)
                measure = np.interp(measure, [0,41942], [0,131.07]) # This is basically the same as the setpoint, but can measure over 100%

                # Parsing fmeasure and temperature is a little more complicated -
                # grab their respective slices from the chained response, then convert from IEEE754 floating point notation to decimal
                fsetpoint = self.hex_to_ieee754_dec(fsetpoint[11:19])
                fmeasure = self.hex_to_ieee754_dec(fmeas_and_temp[11:19])
                temp = self.hex_to_ieee754_dec(fmeas_and_temp[23:])

                self.big_data["Bronkhorst Pressure"]["Time (epoch)"] = timestamp
                self.big_data["Bronkhorst Pressure"]["Data"]["Setpoint (mbar a)"] = fsetpoint
                self.big_data["Bronkhorst Pressure"]["Data"]["Measurement (%)"] = measure
                self.big_data["Bronkhorst Pressure"]["Data"]["Measurement (mbar a)"] = fmeasure
                self.big_data["Bronkhorst Pressure"]["Data"]["Temperature (C)"] = temp
                
            except KeyError as e:
                logger.warning(f"Error in saving bronkhorst data to big dictionary: No key {e}. Not updating measurement")
            except Exception as e:
                logger.warning(f"Unexpected exception in Bronkhorst data: {e}. Not updating measurement")

    def mantissa_to_int(self, mantissa_str):
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

    def hex_to_ieee754_dec(self, hex_str:str) -> float:
        """
        Method to convert a hexadecimal string (e.g what is returned from the Bronkhorst) into an IEEE floating point. It's gnarly,
        more details https://www.mimosa.org/ieee-floating-point-format/ and https://www.h-schmidt.net/FloatConverter/IEEE754.html
        
        In short, the IEEE 754 standard formats a floating point as N = 1.F x 2E-127, 
        where N = floating point number, F = fractional part in binary notation, E = exponent in bias 127 representation.

        The hex input corresponds to a 32 bit binary:
                Sign | Exponent  |  Fractional parts of number
                0    | 00000000  |  00000000000000000000000
            Bit: 31   | [30 - 23] |  [22        -         0]

        Args:
            hex_str (str, hexadecimal representation of binary string)

        Returns:
            dec (float, number in decimal notation)
        """

        # Convert to integer, keeping its hex representation
        ieee_32_hex = int(hex_str, 16)
        # Convert to 32 bit binary
        ieee_32 = f'{ieee_32_hex:0>32b}'
        # The first bit is the sign bit
        sign_bit = int(ieee_32[0])
        # The next 8 bits are exponent bias in biased form - subtract 127 to get the unbiased form
        exponent_bias = int(ieee_32[1:9], 2)
        exponent_unbias = exponent_bias - 127
        # Next 23 bits are the mantissa
        mantissa_str = ieee_32[9:]
        mantissa_int = self.mantissa_to_int(mantissa_str)
        # Finally, convert to decimal
        dec = pow(-1, sign_bit) * mantissa_int * pow(2, exponent_unbias)

        return dec

if __name__ == "__main__":
    interp = Interpreter()
    print(interp.big_data)