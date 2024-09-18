# -------------
# This is the Graphical User Interface (GUI) - true to its name, many graphs and user interface going on here!
# I've tried to make it as modular as possible, so adding additional sensors in the future won't be as much of a pain. 
# -------------

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT  as NavigationToolbar
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

import matplotlib.pyplot as plt
import numpy as np
import yaml
import sys
import time
from collections import deque
from functools import partial
import csv
import concurrent.futures

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

from main_pipeline.sensor import Sensor
from main_pipeline.interpreter import Interpreter
from main_pipeline.display import Display
from main_pipeline.bus import Bus

# pyqt threading
class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handle worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        # Retrieve args/kwargs here; and fire processing using them
        self.fn(*self.args, **self.kwargs)

# main window
class ApplicationWindow(QWidget):
    """
    This is the Graphical User Interface, or GUI! It sets up the user interface for the main pipeline.

    Args:
        This class inherets from the general QWidget class in order to make the main window. There are lots of different 
        ways to this inheriting, which make some of the syntax slightly different in between applications. Ah well.
        
    """
    def __init__(self):
        # Initialize the inherited class (QWidget)
        super().__init__()

        # Window settings
        self.setGeometry(50, 50, 2000, 1200) # window size (x-coord, y-coord, width, height)
        self.setWindowTitle("MGR App")

        # Set some fonts
        self.bold16 = QFont("Helvetica", 16)
        self.bold16.setBold(True)
        self.norm16 = QFont("Helvetica", 16)
        self.bold12 = QFont("Helvetica", 12)
        self.bold12.setBold(True)
        self.norm12 = QFont("Helvetica", 12)

        # Initialize the main sense-interpret-save data pipeline
        self.init_data_pipeline()
        
        # Set data buffer parameters
        self.max_buffer_length = 5000 # How long we let the buffers get, helps with memory
        self.default_plot_length = 60 # Length of time (in sec) we plot before you have to scroll back to see it
        # self.load_notes_directory()
        self.load_notes_entries()
        self.init_data_buffer()
        
        # Create the three main GUI panels:
        # 1. Left panel: sensor status and control
        left_layout = QGridLayout()
        self.build_control_layout(left_layout)
        # 2. Center panel: data streaming
        center_layout = QVBoxLayout()
        self.build_plotting_layout(center_layout)
        # 3. Right panel: logging and notetaking
        right_layout = QVBoxLayout()
        self.build_notes_layout(right_layout)

        # Wrap these three main panels up into one big layout, and add it to the app window
        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout)
        main_layout.addLayout(center_layout)
        main_layout.addLayout(right_layout)
        self.setLayout(main_layout)
        
        # Haven't used this yet, but might still - create a threadpool for this class, so we can do threading later
        self.threadpool = QThreadPool()
            
        # Initiate two timers:
        update_period = 500 # ms
        # One for updating the plots...
        self.plot_figs_timer = QTimer()
        self.plot_figs_timer.timeout.connect(self.update_plots)
        self.plot_figs_timer.start(update_period)
        # ...and one for collecting, processing, and saving data
        self.execution_timer = QTimer()
        self.execution_timer.timeout.connect(self.run_data_collection)
        self.execution_timer.start(update_period)
        
        # Show the window
        self.show()

    ## --------------------- FILE DIRECTORY & DATA INITS --------------------- ## 
    
    
    
    ## --------------------- SENSOR STATUS & CONTROL --------------------- ## 
       
    def build_control_layout(self, left_layout:QLayout):
        title_button_info, sensor_button_info = self._define_button_callbacks()
        start_next_row, title_colspan = self._make_title_control_layout(left_layout, title_button_info)
        self._make_sensor_control_layout(left_layout, sensor_button_info, starting_row=start_next_row, colspan=title_colspan)

        # Position the panel at the top of the window
        left_layout.setAlignment(QtCore.Qt.AlignTop)

    def _make_title_control_layout(self, parent:QGridLayout, title_button_info:dict, colspan=2):
        # Set the title
        label = QLabel(self)
        label.setText("Sensor Status & Control")
        label.setFont(self.bold16)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        # label.setMargin()
        parent.addWidget(label, 0, 0, 1, colspan) # args: widget, row, column, rowspan, columnspan

        num_rows, num_cols = find_grid_dims(num_elements=len(title_button_info), num_cols=colspan)

        # For all the buttons we want (stored in the title_buttons dict) create, position, and assign a callback for each
        i = 0
        title_button_text = list(title_button_info.keys())
        self.title_buttons = {} # hold onto the buttons for later
        for row in range(1, num_rows+1): # Adjusting for the title row
            for col in range(num_cols):
                button_text = title_button_text[i]
                button = QPushButton(self)
                button.setText(button_text)
                button.setFont(self.norm12)
                button.pressed.connect(title_button_info[button_text]["callback"])
                button.setEnabled(title_button_info[button_text]["enabled"])
                parent.addWidget(button, row, col)
                self.title_buttons.update({button_text:button})
                i+=1

        line = QFrame(self)
        line.setFrameShape(QFrame.HLine)
        parent.addWidget(line, row+1, 0, 1, colspan)

        start_next_row = row+2

        return start_next_row, colspan
    
    def _make_sensor_control_layout(self, parent:QGridLayout, sensor_buttons:dict, starting_row, colspan):
        self.sensor_status_display = {}
        num_rows, num_cols = find_grid_dims(num_elements=len(self.sensor_names), num_cols=1)
        i = 0
        elements_per_row = 4
        for row in range(starting_row, (elements_per_row*num_rows)+starting_row, elements_per_row):
            for col in range(num_cols):
                sensor = self.sensor_names[i]

                title = QLabel(self)
                title.setFont(self.bold12)
                title.setText(sensor)
                title.setAlignment(Qt.AlignHCenter)
                title.setStyleSheet("padding-top:10px")
                parent.addWidget(title, row, col, 1, colspan)

                status = QLabel(self)
                status.setText("OFFLINE")
                status.setFont(self.norm12)
                status.setStyleSheet("background-color:#AF5189; margin:10px")
                status.setAlignment(Qt.AlignCenter)
                parent.addWidget(status, row+1, col, 1, colspan)
                self.sensor_status_display.update({sensor:status})
                
                try:
                    buttons = sensor_buttons[sensor]
                    c = 0
                    for button in buttons:
                        b = QPushButton(self)
                        b.setText(button)
                        b.setFont(self.norm12)
                        b.pressed.connect(sensor_buttons[sensor][button])
                        parent.addWidget(b, row+2, col+c)
                        c+=1
                except KeyError:
                    print("no command buttons for this sensor")

                line = QFrame(self)
                line.setFrameShape(QFrame.HLine)
                parent.addWidget(line, row+3, col, 1, colspan)

                i+=1

    def _define_button_callbacks(self):
        title_buttons = {}
        title_button_names = ["Initialize All Sensors", "Shutdown All Sensors", "Start Data Collection", "Stop Data Collection"]
        title_button_callbacks = [self._on_sensor_init, self._on_sensor_shutdown, self._on_start_data, self._on_stop_data]
        title_button_enabled = [True, True, False, False]
        for name, callback, enabled in zip(title_button_names, title_button_callbacks, title_button_enabled):
            title_buttons.update({name: {"callback":callback, "enabled":enabled}})

        sensor_buttons = {}
        for name in self.sensor_names:
            sensor_buttons.update({name:{}})
        sensor_buttons.update({"Abakus Particle Counter": {"Start Abakus":self.sensor.abakus.initialize_abakus,
                                                           "Stop Abakus":self.sensor.abakus.stop_measurement}})
        sensor_buttons.update({"Laser Distance Sensor":{"Start Laser":self.sensor.laser.initialize_laser,
                                                        "Stop Laser":self.sensor.laser.stop_laser}})
        sensor_buttons.update({"Flowmeter":{"Start SLI2000":self.sensor.flowmeter_sli2000.initialize_flowmeter,
                                            "Start SLS1500":self.sensor.flowmeter_sls1500.initialize_flowmeter}})

        return title_buttons, sensor_buttons
    
    def _on_sensor_init(self):
        ######## PUT THIS IN A THREAD SO IT DOESN'T KILL THE GUI ##########
        self.sensor_status_dict = self.sensor.initialize_sensors()
        print(self.sensor_status_dict)
        self._update_sensor_status()
        self.title_buttons["Start Data Collection"].setEnabled(True)
        self.title_buttons["Stop Data Collection"].setEnabled(True)

    def _on_sensor_shutdown(self):
        self.data_collection = False
        self.sensor_status_dict = self.sensor.shutdown_sensors()
        self._update_sensor_status()
        self.title_buttons["Start Data Collection"].setEnabled(False)
        self.title_buttons["Stop Data Collection"].setEnabled(False)
    
    def _on_start_data(self):
        self.data_collection = True
        # worker = Worker(self.run_data_collection())
        # self.threadpool.start(worker)
        
    def _on_stop_data(self):
        self.data_collection = False

    def _update_sensor_status(self):
        """Method to update the sensor status upon initialization or shutdown. Uses the values stored in
        self.sensor_status_dict to set the color and text of each sensor status widget."""
        # Loop through the sensors and grab their status from the sensor status dictionary
        for name in self.sensor_names:
            status = self.sensor_status_dict[name]
            # If we're offline
            if status == 0:
                # color = "#D80F0F"
                color = "#AF5189"
                text = "OFFLINE"
            # If we're online / successfully initialized
            elif status == 1:
                color = "#619CD2"
                text = "ONLINE"
            # If we're disconnected / using shadow hardware
            elif status == 2:
                color = "#FFC107"
                text = "SHADOW HARDWARE"
            # IF we failed initialization / there's some other error going on
            elif status == 3:
                color = "#D55E00"
                text = "ERROR"
            # If we recieved an erroneous reading, make it obvious
            else:
                color = "purple"
                text = "?????"

            # Update the sensor status accordingly
            status = self.sensor_status_display[name] # This is a dictionary of QLabels
            status.setText(text)
            status.setStyleSheet(f"background-color:{color}; margin:10px")

    ## --------------------- LOGGING & NOTETAKING --------------------- ##

    def build_notes_layout(self, right_layout:QLayout):
        # Set the title
        label = QLabel(self)
        label.setText("Notes & Logs")
        label.setFont(self.bold16)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        right_layout.addWidget(label)
        
        # init notes dictionary - should move to its own method
        self.logging_entries = {}
        self.logging_entries.update({"Internal Timestamp (epoch)":""})
        for key in self.notes_dict:
            self.logging_entries.update({key:""})

        self.lineedits = []
        for note in self.notes_dict:
            line = QLineEdit(self)
            line.setFont(self.norm12)
            line.setPlaceholderText(note)
            line.setTextMargins(10, 10, 10, 10)
            # When the user has finished editing the line, pass the line object and the title to self._save_notes
            line.editingFinished.connect(partial(self._save_notes, line, note))
            line.setMaximumWidth(700)
            right_layout.addWidget(line, alignment=Qt.AlignTop)

        # Make a button to save the text entries to a csv
        log_button = QPushButton(self)
        log_button.setText("LOG")
        log_button.setFont(self.bold12)
        log_button.pressed.connect(self._log_notes)
        right_layout.addWidget(log_button, alignment=QtCore.Qt.AlignTop)

        # Position the panel at the top of the window
        right_layout.setAlignment(QtCore.Qt.AlignTop)

    def _save_notes(self, line:QLineEdit, note_title:str):
        """
        Method to hold onto the values entered into the logging panel

        Args:
            line (QLineEdit): _description_
            note_title (str): _description_
        """

        self.logging_entries.update({note_title: line.text()})
        self.lineedits.append(line)

    def _log_notes(self):
        """Callback for the 'log' button (self.init_logging_panel), logs the text entries (self.logging_entries) to a csv"""
        self.display.save_notes(self.logging_entries.values())
        
        timestamp = time.time()
        self.logging_entries.update({"Timestamp (epoch)": timestamp})

        # Clear the dictionary of notes and the text entries on the screen
        # self.logging_entries.clear()
        for key in self.logging_entries:
            self.logging_entries[key] = ""
        for line in self.lineedits:
            line.clear()
   
    def load_notes_entries(self):
        """
        Method to read in the log_entries.yaml config file and grab onto that dictionary. If it can't
        find that file, it returns an empty dictionary - no logging entries will be displayed.
        
        Updates - 
            - self.notes_dict: dict, entries to display on the logging panel
        """
        # Read in the logging config file to initialize the notes entries 
        try:
            with open("config/log_entries.yaml", 'r') as stream:
                self.notes_dict = yaml.safe_load(stream)
        except FileNotFoundError as e:
            logger.warning(f"Error in reading log_entries config file: {e}. Leaving logging panel empty.")
            self.notes_dict = {}
    
    ## --------------------- DATA INPUT & STREAMING DISPLAY --------------------- ##

    def build_plotting_layout(self, center_layout:QLayout):
        """
        A method to build the central plotting panel. Takes in the parent layout (center_layout) and adds a QTabWidget
        to give us a convienent way to display the live sensor plots. For each sensor (stored in self.sensor_names), we add a tab
        to hold the matplotlib figure and toolbar that will display sensor data.

        Args:
            center_layout (QLayout): The main window layout we want to nest the plots in
        """
        # Make a title
        label = QLabel(self)
        label.setText("Live Sensor Data")
        label.setFont(self.bold16)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        center_layout.addWidget(label)

        # Initialize the plotting flag
        self.data_collection = False

        # Create some object variables to hold plotting information - the QTabWidget that displays the figs, and a dictionary
        # to hold onto the figure objects themselves for later updating
        self.plot_tab = QTabWidget(self)
        self.plot_figs = {}
        # Loop through the sensors, create a figure & toolbar for each, and add them to the QTabWidget
        for sensor in self.sensor_names:
            # Create a new tab and give it a vertical layout
            tab = QWidget(self)
            tab.setObjectName(sensor)
            tab_vbox = QVBoxLayout(tab)
            # For each figure, we want a subplot corresponding to each piece of data returned by the sensor. Grab that number
            num_subplots = len(self.big_data_dict[sensor]["Data"])
            # Create the figure and toolbar
            fig = MyFigureCanvas(x_init=[[time.time()]]*num_subplots,   # List of lists, one for each subplot, to initialize the figure x-data
                                 y_init=[[0]]*num_subplots, # List of lists, one for each subplot, to initialize the figure y-data
                                 xlabels=["Time (epoch)"]*num_subplots,
                                 ylabels=list(self.big_data_dict[sensor]["Data"].keys()),
                                 num_subplots=num_subplots,
                                 x_range=self.default_plot_length, # Set xlimit range of each axis
                                 )
            toolbar = NavigationToolbar(canvas=fig, parent=self, coordinates=False)
            # Add the figure and toolbar to this tab's layout
            tab_vbox.addWidget(toolbar, alignment=Qt.AlignHCenter)
            tab_vbox.addWidget(fig)
            # Add this tab to the QTabWidget
            self.plot_tab.addTab(tab, sensor)
            # Hold onto the figure object for later
            self.plot_figs.update({sensor: fig})
        # Once we've done all that, add the QTabWidget to the main layout
        center_layout.addWidget(self.plot_tab)
        
        # Finally, add a custom tab to plot multiple readings from multiple sensors
        self.add_all_plots_tab()

    def add_all_plots_tab(self):
        """Method to read in the main_page_plots config file and use it to initialize a special tab to show a few
        """
        # Create a new tab and give it a vertical layout
        tab = QWidget(self)
        tab.setObjectName("All")
        tab_vbox = QVBoxLayout(tab)

        ##### should have some sort of validation here to make sure all the keys are in the big data dict, and eliminate them otherwise ######
        with open("config/main_page_plots.yaml", 'r') as stream:
            self.main_page_plots = yaml.safe_load(stream)

        num_subplots = 0
        y_axis_labels = []
        for key in self.main_page_plots:
            main_page_plot_titles = self.main_page_plots[key]
            for title in main_page_plot_titles:
                y_axis_labels.append(title)
                num_subplots += 1

        self.main_page_num_subplots = num_subplots

        fig = MyFigureCanvas(x_init=[[time.time()]]*num_subplots,   # List of lists, one for each subplot, to initialize the figure x-data
                                 y_init=[[0]]*num_subplots, # List of lists, one for each subplot, to initialize the figure y-data
                                 xlabels=["Time (epoch)"]*num_subplots,
                                 ylabels=y_axis_labels,
                                 num_subplots=num_subplots,
                                 x_range=self.default_plot_length, # Set xlimit range of each axis
                                 )

        tab_vbox.addWidget(fig)
        self.plot_figs.update({"All":fig})
        self.plot_tab.insertTab(0, tab, "Specified Plots")
        self.plot_tab.setCurrentIndex(0)

    def update_plots(self):
        """Method to update the live plots with the buffers stored in self.big_data_dict
        """
        # If the data collection flag is active...
        if self.data_collection:
            # Grab the name of the current QTabWidget tab we're on (which sensor data we're displaying)
            plot_name = self.plot_tab.currentWidget().objectName()
            fig = self.plot_figs[plot_name]
            # Make sure the figure is the correct object - not strictly necessary, but a good safety check
            if type(fig) == MyFigureCanvas:
                # Grab the updated x and y values from the big data buffer
                x_data_list, y_data_list = self.get_xy_data_from_buffer(plot_name)
                # Pass the updated data into the figure object and redraw the axes
                fig.update_data(x_new=x_data_list, y_new=y_data_list)
                fig.update_canvas()

    def get_xy_data_from_buffer(self, plot_name:str):
        """Method to parse the big data buffer and pull out the sensor channels we're interested in plotting.

        Args:
            plot_name (str): The name of the QWidget we're plotting on, should match a sensor in self.sensor names or be "All" for the
                main page plots

        Returns:
            x_data_list (list): _description_ \n

            y_data_list (list): _description_
        """
        # Try to extract the updated data from the big buffer
        try:
            num_subplots = len(self.big_data_dict[plot_name]["Data"].keys())
            x_data_list = [self.big_data_dict[plot_name]["Time (epoch)"]]*num_subplots # Same timestamp for all sensor readings
            y_data_list = list(self.big_data_dict[plot_name]["Data"].values())
        # If we can't do that, we're probably on the "main page plots" tab, in which case the plot name is "All"
        except KeyError as e:
            # If we /are/ on that page, we need to do a little more finagling to extract the data we want
            if plot_name == "All":
                # Grab the sensors we want to plot, from the dictionary we read in earlier (add_all_plots_page)
                sensors = list(self.main_page_plots.keys())
                # The dictionary has key-value pairs of "sensor name":["sensor channel to plot", "other sensor channel to plot"].
                # Loop through both the sensor names /and/ the sensor channels we want to plot, grabbing their data from the big dict
                x_data_list = []
                y_data_list = []
                for sensor in sensors:
                    subplot_names = self.main_page_plots[sensor]
                    for subplot_name in subplot_names:
                        x_data_list.append(self.big_data_dict[sensor]["Time (epoch)"])
                        y_data_list.append(self.big_data_dict[sensor]["Data"][subplot_name])
            # Otherwise (and we should never get here if validation worked correctly), something went wrong
            else:
                logger.warning(f"Error in reading the data buffer when updating plots: {e}")
                x_data_list = []
                y_data_list = []

        return x_data_list, y_data_list

    ## --------------------- DATA COLLECTION PIPELINE --------------------- ##
    def init_data_pipeline(self):
        """Creates objects of the Sensor(), Interpreter(), and Display() classes, and sets busses and delay times 
        for each sense/interpret/save process (see run_data_collection for how these are all used)
        """
        # Create each main object of the pipeline
        self.sensor = Sensor()
        self.interpretor = Interpreter()
        self.display = Display()

        # Initialize the busses
        self.abakus_bus = Bus()
        self.flowmeter_sli2000_bus = Bus()
        self.flowmeter_sls1500_bus = Bus()
        self.laser_bus = Bus()
        self.picarro_gas_bus = Bus()
        self.bronkhorst_bus = Bus()
        self.main_interp_bus = Bus()

        # Set the delay times (sec)
        self.sensor_delay = 0.3
        self.interp_delay = 0.1
        self.display_delay = 0.1

    def init_data_buffer(self):
        """Method to read in and save the sensor_data configuration yaml file
        
        Updates - 
            - self.big_data_dict: dict, holds buffer of data with key-value pairs 'Sensor Name':deque[data buffer]
            - self.sensor_names: list, sensor names that correspond to the buffer dict keys
        """
        # Read in the sensor data config file to initialize the data buffer. 
        # Creates a properly formatted, empty dictionary to store timestamps and data readings to each sensor
        with open("config/sensor_data.yaml", 'r') as stream:
            self.big_data_dict = yaml.safe_load(stream)

        # Comb through the keys, set the timestamp to the current time and the data to zero
        sensor_names = self.big_data_dict.keys()
        for name in sensor_names:
            self.big_data_dict[name]["Time (epoch)"] = deque([time.time()], maxlen=self.max_buffer_length)
            channels = self.big_data_dict[name]["Data"].keys()
            for channel in channels:
                self.big_data_dict[name]["Data"][channel] = deque([0.0], maxlen=self.max_buffer_length)

        # Grab the names of the sensors from the dictionary
        self.sensor_names = list(sensor_names)

    def run_data_collection(self):
        if self.data_collection:
            with concurrent.futures.ThreadPoolExecutor() as self.executor:
                eAbakus = self.executor.submit(self.sensor.abakus_producer, self.abakus_bus, self.sensor_delay)

                eFlowMeterSLI2000 = self.executor.submit(self.sensor.flowmeter_sli2000_producer, self.flowmeter_sli2000_bus, self.sensor_delay)
                eFlowMeterSLS1500 = self.executor.submit(self.sensor.flowmeter_sls1500_producer, self.flowmeter_sls1500_bus, self.sensor_delay)
                eLaser = self.executor.submit(self.sensor.laser_producer, self.laser_bus, self.sensor_delay)
                ePicarroGas = self.executor.submit(self.sensor.picarro_gas_producer, self.picarro_gas_bus, self.sensor_delay)
                eBronkhorst = self.executor.submit(self.sensor.bronkhorst_producer, self.bronkhorst_bus, self.sensor_delay)
                eInterpretor = self.executor.submit(self.interpretor.main_consumer_producer, self.abakus_bus, self.flowmeter_sli2000_bus,
                                            self.flowmeter_sls1500_bus, self.laser_bus, self.picarro_gas_bus, self.bronkhorst_bus, 
                                            self.main_interp_bus, self.interp_delay)

                eDisplay = self.executor.submit(self.display.display_consumer, self.main_interp_bus, self.display_delay)


            data = eDisplay.result()
            # print(data)
            self.update_buffer(data, use_noise=False)
            # print(self.big_data_dict)

    def update_buffer(self, new_data:dict, use_noise=False):
        """Method to update the self.big_data_dict buffer with new data from the sensor pipeline.
        
        Args - 
            - new_data: dict, most recent data update. Should have the same key/value structure as big_data_dict
            - use_noise: bool, adds some random noise if true. For testing
        """
        # For each sensor name, grab the timestamp and the data from each sensor channel. If it's in a list, take the
        # first index, otherwise, append the dictionary value directly
        for name in self.sensor_names:
            # Grab and append the timestamp
            try:    # Check if the dictionary key exists... 
                new_time = new_data[name]["Time (epoch)"]  
                self.big_data_dict[name]["Time (epoch)"].append(new_time)
            except KeyError as e:   # ... otherwise log an exception
                logger.warning(f"Error updating the {name} buffer timestamp: {e}")
            except TypeError as e:  # Sometimes due to threading shenanigans it comes through as "NoneType", check for that too
                logger.warning(f"Error updating the {name} buffer timestamp: {e}")
            
            # Grab and append the data from each channel
            channels = list(self.big_data_dict[name]["Data"].keys())
            for channel in channels:
                if use_noise: # If we're using noise, set that (mostly useful for visual plot verification with simulated sensors)
                    noise = np.random.rand()
                else:
                    noise = 0
                try:    # Check if the dictionary key exists... 
                    ch_data = new_data[name]["Data"][channel] + noise
                    self.big_data_dict[name]["Data"][channel].append(ch_data)
                except KeyError:    # ... otherwise log an exception
                    logger.warning(f"Error updating the {name} buffer data: {e}")
                except TypeError as e: 
                    logger.warning(f"Error updating the {name} buffer data: {e}")


class MyFigureCanvas(FigureCanvas):
    """This is the FigureCanvas in which the live plot is drawn."""
    def __init__(self, x_init:deque, y_init:deque, xlabels:list, ylabels:list, num_subplots=1, x_range=60) -> None:
        """
        :param x_init:          
        :param y_init:          Initial y-data
        :param x_range:         How much data we show on the x-axis, in x-axis units

        """
        super().__init__(plt.Figure())

        # Initialize constructor arguments
        self.x_data = x_init
        self.y_data = y_init
        self.x_range = x_range
        self.num_subplots = num_subplots

        # Store a figure axis for the number of subplots set
        self.axs = []
        for i in range(0, num_subplots):
            ax = self.figure.add_subplot(num_subplots+1, 1, i+1)
            self.axs.append(ax)
            ax.set_xlabel(xlabels[i])
            ax.set_ylabel(ylabels[i])

        # self.figure.set_figheight(5*num_subplots)
        # self.figure.tight_layout(pad=4)
        
        self.draw()   

    def update_data(self, x_new=None, y_new=None):
        """Method to update the variables to plot. If nothing is given, get fake ones for testing"""    
        if x_new is None:
            new_x = self.x_data[0][-1]+1
            for i in range(self.num_subplots):
                self.x_data[i].append(new_x)
        else:
            self.x_data = x_new

        if y_new is None:
            for i in range(self.num_subplots):
                self.y_data[i].append(get_next_datapoint())
        else:
            self.y_data = y_new

    def update_canvas(self) -> None:
        """Method to update the plots based on the buffers stored in self.x_data and self.y_data"""
        # Loop through the number of subplots in this figure
        for i, ax in enumerate(self.axs):
            # Clear the figure without resetting the axis bounds or ticks
            for artist in ax.lines:
                artist.remove()
            # Plot the updated data and make sure we aren't either plotting offscreen or letting the x axis get too long
            ax.plot(self.x_data[i], self.y_data[i], '.--')
            xlim = ax.get_xlim()
            if (xlim[1] - xlim[0]) >= self.x_range:
                ax.set_xlim([self.x_data[i][-1] - self.x_range, self.x_data[i][-1] + 1])

        self.draw()

        # Faster code but can't get the x-axis updating to work
        # ---------
        # self._line_.set_ydata(self.y_data)
        # self._line_.set_xdata(self.x_data)
        # self.ax.draw_artist(self.ax.patch)
        # self.ax.draw_artist(self._line_)
        # self.ax.set_ylim(ymin=min(self.y_data), ymax=min(self.y_data))
        # self.ax.set_xlim(xmin=self.x_data[0], xmax=self.x_data[-1])
        # self.draw()
        # self.update()
        # self.flush_events()

## --------------------- HELPER FUNCTIONS --------------------- ##

def find_grid_dims(num_elements, num_cols):
    """Method to determine the number of rows we need in a grid given the number of elements and the number of columns
    
        Returns - num_rows (int), num_cols (int)"""

    num_rows = num_elements / num_cols
    # If the last number of the fraction is a 5, add 0.1. This is necessary because Python defaults to 
    # "bankers rounding" (rounds 2.5 down to 2, for example) so would otherwise give us too few rows
    if str(num_rows).split('.')[-1] == '5':
        num_rows += 0.1
    num_rows = round(num_rows)

    return num_rows, num_cols

# Data source
# ------------
n = np.linspace(0, 499, 500)
d = 50 + 25 * (np.sin(n / 8.3)) + 10 * (np.sin(n / 7.5)) - 5 * (np.sin(n / 1.5))
i = 0
def get_next_datapoint():
    global i
    i += 1
    if i > 499:
        i = 0
    return float(d[i])

if __name__ == "__main__":
    qapp = QtWidgets.QApplication(sys.argv)
    app = ApplicationWindow()
    qapp.exec_()