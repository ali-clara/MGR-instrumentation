
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
    """The PyQt5 main window"""

    def __init__(self):
        super().__init__()

        self.sensor = Sensor()
        
        # Window settings
        self.setGeometry(50, 50, 2000, 1200) # Set window size (x-coord, y-coord, width, height)
        self.setWindowTitle("MGR App")

        # Set some fonts
        self.bold16 = QFont("Helvetica", 16)
        self.bold16.setBold(True)
        self.norm16 = QFont("Helvetica", 16)
        self.bold12 = QFont("Helvetica", 12)
        self.bold12.setBold(True)
        self.norm12 = QFont("Helvetica", 12)

        main_layout = QHBoxLayout()
        left_layout = QGridLayout()
        center_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        self.max_buffer_length = 5000
        self._load_notes_directory()
        self._load_notes_entries()
        self._init_data_buffer()

        self.build_plotting_layout(center_layout)
        self.build_control_layout(left_layout)
        self.build_notes_layout(right_layout)

        main_layout.addLayout(left_layout)
        main_layout.addLayout(center_layout)
        main_layout.addLayout(right_layout)

        self.setLayout(main_layout)
        
        self.threadpool = QThreadPool()
            
        # Initiate the timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(50)
        
        # Show the window
        self.show()

    ## --------------------- FILE DIRECTORY & DATA INITS --------------------- ## 
    
    def _load_notes_directory(self):
        """
        Method to read the data_saving.yaml config file and set the notes/logs filepath accordingly. If
        it can't find that file, it defaults to the current working directory.
        
        Updates - 
            - self.notes_filepath: str, where the notes/logs get saved    
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
    
    def _init_data_buffer(self):
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
    
    ## --------------------- SENSOR STATUS & CONTROL --------------------- ##    

    def build_control_layout(self, left_layout:QLayout):
        title_buttons, sensor_buttons = self._define_button_callbacks()
        start_next_row, title_colspan = self._make_title_control_layout(left_layout, title_buttons)
        self._make_sensor_control_layout(left_layout, sensor_buttons, starting_row=start_next_row, colspan=title_colspan)

        # Position the panel at the top of the window
        left_layout.setAlignment(QtCore.Qt.AlignTop)

    def _make_title_control_layout(self, parent:QGridLayout, title_buttons:dict, colspan=2):
        # Set the title
        label = QLabel(self)
        label.setText("Sensor Status & Control")
        label.setFont(self.bold16)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        # label.setMargin()
        parent.addWidget(label, 0, 0, 1, colspan) # args: widget, row, column, rowspan, columnspan

        num_rows, num_cols = find_grid_dims(num_elements=len(title_buttons), num_cols=colspan)

        # For all the buttons we want (stored in the title_buttons dict) create, position, and assign a callback for each
        i = 0
        title_button_text = list(title_buttons.keys())
        for row in range(1, num_rows+1): # Adjusting for the title
            for col in range(num_cols):
                button = QPushButton(self)
                button.setText(title_button_text[i])
                button.setFont(self.norm12)
                button.pressed.connect(title_buttons[title_button_text[i]])
                parent.addWidget(button, row, col)
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
        for name, callback in zip(title_button_names, title_button_callbacks):
            title_buttons.update({name: callback})

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
        self.sensor_status_dict = self.sensor.initialize_sensors()
        self._update_sensor_status()

    def _on_sensor_shutdown(self):
        self.sensor_status_dict = self.sensor.shutdown_sensors()
        self._update_sensor_status()
    
    def _on_start_data(self):
        self.plotting = True
        
    def _on_stop_data(self):
        self.plotting = False

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
        
        self.logging_entries = {}
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
        """Method to hold onto the values entered into the logging panel"""
        self.logging_entries.update({note_title: line.text()})
        self.lineedits.append(line)

    def _log_notes(self):
        """Callback for the 'log' button (self.init_logging_panel), logs the text entries (self.logging_entries) to a csv"""
        # Loops through the elements in self.logging_entries (tkinter Text objects), reads and clears each element
        timestamp = time.time()
        self.logging_entries.update({"Timestamp (epoch)": timestamp})

        # Check if a file exists at the given path and write the notes
        try:
            with open(self.notes_filepath, 'a') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', lineterminator='\r')
                writer.writerow(self.logging_entries.values())
        # If it doesn't, something went wrong with initialization - remake it here
        except FileNotFoundError:
            with open(self.notes_filepath, 'x') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                notes_titles = list(self.notes_dict.keys())
                notes_titles.append("Internal Timestamp (epoch)")
                writer.writerow(notes_titles) # give it a title
                writer.writerow(self.logging_entries.values()) # write the notes

        # Clear the dictionary of notes and the text entries on the screen
        self.logging_entries.clear()
        for line in self.lineedits:
            line.clear()
   
    def _load_notes_entries(self):
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
        ### Center layout
        label = QLabel(self)
        label.setText("Live Sensor Data")
        label.setFont(self.bold16)
        label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        center_layout.addWidget(label)

        # Set the plotting button
        self.plotting = False
        # b = QPushButton("Start plotting")
        # b.pressed.connect(self.start_plots)
        # center_layout.addWidget(b)

        # Make the dropdown
        combobox = QComboBox()
        combobox.addItems(self.sensor_names)
        center_layout.addWidget(combobox)

        # Set the plots
        self.plots = {"test":[]}
        for i in range(5):
            n = int(np.random.randint(1,3))
            x_init = [[0]]*n
            y_init = [[0]]*n
            fig = MyFigureCanvas(x_init, y_init, num_subplots=n, buffer_length=self.max_buffer_length)
            toolbar = NavigationToolbar(fig, self, False)
            self.plots["test"].append(fig)
            center_layout.addWidget(toolbar, alignment=Qt.AlignHCenter)
            center_layout.addWidget(fig, alignment=Qt.AlignHCenter)
    
    def start_plots(self):
        """Set the plotting flag to True"""
        self.plotting = True

    def update_plots(self):
        """Method to update the plots with new data"""
        if self.plotting:
            for i, fig in enumerate(self.plots["test"]):
                fig.update_data() # If left blank, udates and plots with random data
                fig.update_canvas()


class MyFigureCanvas(FigureCanvas):
    """This is the FigureCanvas in which the live plot is drawn."""
    def __init__(self, x_init:deque, y_init:deque, num_subplots=1, x_range=60, buffer_length=5000) -> None:
        """
        :param x_init:          
        :param y_init:          Initial y-data
        :param x_range:         How much data we show on the x-axis, in x-axis units
        :param buffer_length: 

        """
        super().__init__(plt.Figure())

        # Initialize constructor arguments
        self.x_data = x_init
        self.y_data = y_init
        self.x_range = x_range
        self.num_subplots = num_subplots

        # Store a figure axis for the number of subplots set
        self.axs = []
        for i in range(1, num_subplots+1):
            ax = self.figure.add_subplot(num_subplots, 1, i)
            self.axs.append(ax)
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
            ax.plot(self.x_data[i], self.y_data[i])
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