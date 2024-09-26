# -------------
# The display class
# -------------

import time
import yaml
import csv
import pandas as pd

# from gui import GUI
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

class Writer():
    """Class that reads the interpreted data and saves it to the disk"""
    @log_on_end(logging.INFO, "Display class initiated", logger=logger)
    def __init__(self) -> None:

        self.load_data_directory()
        self.load_notes_directory()
        self.init_data_saving()
        self.init_notes_saving()

    def load_notes_directory(self):
        """
        Method to read the data_saving.yaml config file and set the notes/logs filepath accordingly. If
        it can't find that file, it defaults to the current working directory.
        
        Updates - 
            self.notes_filepath: str, where the notes/logs get saved    
        """
        # Set up the first part of the file name - the current date
        # Grab the current time in YYYY-MM-DD HH:MM:SS format
        datetime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        # Grab only the date part of the time
        date = datetime.split(" ")[0]
        # Try to read in the data saving config file to get the directory and filename suffix
        try:
            with open("config/data_saving.yaml", 'r') as stream:
                saving_config_dict = yaml.safe_load(stream)
            # Create filepaths in the data saving directory with the date (may change to per hour depending on size)
            directory = saving_config_dict["Notes"]["Directory"]
            suffix = saving_config_dict["Notes"]["Suffix"]
            self.notes_filepath = f"{directory}\\{date}{suffix}.csv"
        # If we can't find the file, note that and set the filepath to the current working directory
        except FileNotFoundError as e:
            logger.warning(f"Error in loading data_saving config file: {e}. Saving to current working directory")
            self.notes_filepath = f"{date}_notes.csv"
        # If we can't read the dictonary keys, note that and set the filepath to the current working directory
        except KeyError as e:
            logger.warning(f"Error in reading data_saving config file: {e}. Saving to current working directory")
            self.notes_filepath = f"{date}_notes.csv"

    def load_data_directory(self):
        """
        Method to read the data_saving.yaml config file and set the data filepath accordingly. If
        it can't find that file, it defaults to the current working directory.
        
        Updates - 
            self.csv_filepath: str, where the sensor data gets saved as a csv
        """
        # Set up the first part of the file name - the current date
        # Grab the current time in YYYY-MM-DD HH:MM:SS format
        datetime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        # Grab only the date part of the time
        date = datetime.split(" ")[0]
        # Try to read in the data saving config file to get the directory and filename suffix
        try:
            with open("config/data_saving.yaml", 'r') as stream:
                saving_config_dict = yaml.safe_load(stream)
            # Create filepaths in the data saving directory with the date (may change to per hour depending on size)
            directory = saving_config_dict["Sensor Data"]["Directory"]
            suffix = saving_config_dict["Sensor Data"]["Suffix"]
            self.csv_filepath = f"{directory}\\{date}{suffix}.csv"
        # If we can't find the file, note that and set the filepath to the current working directory
        except FileNotFoundError as e:
            logger.warning(f"Error in loading data_saving config file: {e}. Saving to current working directory")
            self.csv_filepath = f"{date}_notes.csv"
        # If we can't read the dictonary keys, note that and set the filepath to the current working directory
        except KeyError as e:
            logger.warning(f"Error in reading data_saving config file: {e}. Saving to current working directory")
            self.csv_filepath = f"{date}_notes.csv"
    
    def get_data_directory(self):
        return self.csv_filepath

    def init_data_saving(self):
        """Method to set up data storage and configure internal data management"""
        # Read in the sensor config file to grab a list of all the sensors we're working with
        try:
            with open("config/sensor_data.yaml", 'r') as stream:
                big_data_dict = yaml.safe_load(stream)
        except FileNotFoundError as e:
            logger.error(f"Error in loading the sensor data config file: {e}")
            big_data_dict = {}
        # Save the keys as a list of sensor names
        self.sensor_names = big_data_dict.keys()

        # Pull out all the data we want to save - the timestamp and channel names of each sensor
        self.data_titles = []
        for name in self.sensor_names:
            channels = big_data_dict[name]["Data"].keys()
            self.data_titles.append(f"{name}: time (epoch)")
            for channel in channels:
                self.data_titles.append(f"{name}: {channel}")

        # Use our titles to initialize a csv file
        self.init_csv(self.csv_filepath, self.data_titles)
    
    def init_notes_saving(self):
        """Method to set up notes storage
        """
        # Read the log_entries config file to grab all the entries we'll be logging
        try:
            with open("config/log_entries.yaml", 'r') as stream:
                notes_dict = yaml.safe_load(stream)
        except FileNotFoundError as e:
            logger.error(f"Error in loading the notes entries config file: {e}")
            notes_dict = {}
        
        # Use the keys of that dictionary to create a list of titles for our csv file
        self.notes_titles = list(notes_dict.keys())
        self.notes_titles.append("Internal Timestamp (epoch)")
        # Initialize a csv file
        self.init_csv(self.notes_filepath, self.notes_titles)

    def init_csv(self, filepath, header):
        """Method to initialize a csv with given header"""
        # Check if we can read the file
        try:
            with open(filepath, 'r'):
                pass
        # If the file doesn't exist, create it and write in whatever we've passed as row titles
        except FileNotFoundError:
            with open(filepath, 'a') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', lineterminator='\r')
                writer.writerow(header)

    def save_data(self, data_dict):
        """Method to save the passed in data to a csv file
        
        Args:
            data_dict (dict): Dictionary of data read in from the interpretor bus in display_consumer.
                Must have the same key-value pairs as the expected dictionary from config/sensor_data.yaml
        """
        # Loop through the data dict and grab out all the sensor channel information (this is the same as when we
        # initialize the csv headers)
        to_write = []
        try:
            for name in self.sensor_names:
                sensor_timestamp = data_dict[name]["Time (epoch)"]
                to_write.append(sensor_timestamp)
                channel_data = data_dict[name]["Data"].values()
                for data in channel_data:
                    to_write.append(data)
        except KeyError as e: # If something has gone wrong with reading the dictionary keys, note that
            logger.warning(f"Error in reading data dictionary: {e}")
        except TypeError as e: # Due to threading timing, sometimes this tries to read the processed data before it's been instantiated. Catch that here
            pass
        # Check if the file exists
        try:
            with open(self.csv_filepath, 'r') as csvfile:
                pass
        # If it doesn't, create it, give it a header, and then write the data
        except FileNotFoundError:
            self.init_csv(self.csv_filepath, self.data_titles)
            with open(self.csv_filepath, 'a') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', lineterminator='\r')
                writer.writerow(to_write)
        # If it does, just write the data
        else:
            with open(self.csv_filepath, 'a') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', lineterminator='\r')
                writer.writerow(to_write)

    def save_notes(self, notes):
        """Method to save the passed in notes to a csv file. Gets called by the GUI whenever the "Log" button is pressed
        
        Args:
            notes (list): List of notes to save
        """
        # Check if a file exists at the given path
        try:
            with open(self.notes_filepath, 'r') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', lineterminator='\r')
        # If it doesn't, something went wrong with initialization or the file got deleted - 
        # remake it here and then write the data
        except FileNotFoundError:
            self.init_csv(self.notes_filepath, self.notes_titles)            
            with open(self.notes_filepath, 'a') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                writer.writerow(notes)
        # If it does exist, write the notes
        else:
            with open(self.notes_filepath, 'a') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', lineterminator='\r')
                writer.writerow(notes)

    def write_consumer(self, interpreter_bus:Bus):
        """Method to read the processed data published by the interpretor class and save it to a csv. Gets called
        by the GUI in the main data pipeline, and will be passed in a Bus object of processed sensor data"""
        interp_data = interpreter_bus.read()
        self.save_data(interp_data)
        return interp_data

if __name__ == "__main__":
    mywriter = Writer()