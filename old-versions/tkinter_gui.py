# -------------
# Old version of the GUI, using Tkinter. Generally works, but didn't end up being fast enought to display all the plots we need. 
# I moved to pyqt5 for better performance and generally more features
# -------------

import numpy as np
import time
from collections import deque
import yaml
import csv
from functools import partial
import copy

import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter.ttk import Notebook
from tkinter.font import Font, BOLD

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

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

class GUI():
    """
    This is the Graphical User Interface, or GUI! It sets up the user interface for the main pipeline.  
        
        Args - 
            - **sensor_button_callback_dict**: dict of methods, where key-value pairs are *'Button Title':callback_function*. 
                This allows us to have buttons to control sensors despite the GUI not importing sensor classes. 
                When the GUI is instantiated, we pass in sensor control functions, which are then triggered by GUI buttons.
    """
    def __init__(self, sensor_button_callback_dict):
        """Initializes everything"""
        ##  --------------------- SIZE & FORMATTING --------------------- ##
        # Make the window and set some size parameters
        self.root = tk.Tk()
        self.root.title("MGR GUI")
        
        # Make the window fullscreen and locked to the desktop size - moving the window around is blocking,
        # so this makes it less likely someone will accidentally pause data collection
        self.root.overrideredirect(True) # can't close the window
        self.root.state('zoomed') # fullscreen
        self.root.resizable(False, False) # unable to be resized

        self.grid_width = 100 # px? computer screen units?
        self.grid_height = 50

        # Make some default colors
        self.button_blue = "#71b5cc"
        self.light_blue = "#579cba"
        self.dark_blue = "#083054"
        self.root.configure(bg=self.light_blue)

        # Make some default fonts
        self.bold20 = Font(self.root, family="Helvetica", size=20, weight=BOLD)
        self.bold16 = Font(self.root, family="Helvetica", size=16, weight=BOLD)
        self.norm16 = Font(self.root, family="Helvetica", size=16)
        self.bold12 = Font(self.root, family="Helvetica", size=12, weight=BOLD)

        # Set some styles
        s = ttk.Style()
        s.configure('TNotebook.Tab', font=self.bold12, padding=[10, 5])
        s.configure('TNotebook', background=self.light_blue)
        s.layout("TNotebook", []) # get rid of the notebook border

        ##  --------------------- INSTRUMENTS & DATA MANAGEMENT --------------------- ##
        # self.data_dir = "data"
        # self._init_data_saving()

        self.max_buffer_length = 5000 # How long we let the buffers get, helps with memory
        self.default_plot_length = 60 # Length of time (in sec) we plot before you have to scroll back to see it
        self._init_data_buffer()

        ## --------------------- GUI LAYOUT --------------------- ##
        # Set up the panel that contains sensor status / control
        status_grid_frame = Frame(self.root, bg='white')
        self.button_callback_dict = sensor_button_callback_dict
        self._init_sensor_status_dict() 
        self._init_sensor_panel(status_grid_frame)

        # Set up the notebook for data streaming/live plotting
        data_streaming_frame = Frame(self.root, bg=self.light_blue)
        self._init_data_streaming_notebook(data_streaming_frame)
        self._init_data_streaming_figs()
        self._init_data_streaming_canvases()
        plt.ion() # Now that we've created the figures, turn on interactive matplotlib plotting

        # Set up a panel for manual logging & note taking
        self._config_notes()
        logging_frame = Frame(self.root, bg=self.dark_blue)
        self._init_notes_panel(logging_frame)

        # Position the frames
        logging_frame.pack(side="right", expand=True, fill=BOTH, padx=5)
        status_grid_frame.pack(side="left", expand=True, fill=BOTH, padx=5)
        data_streaming_frame.pack(side="right", expand=True, fill=BOTH)
  
    
    ## --------------------- DATA INPUT & STREAMING DISPLAY --------------------- ##

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
    
    def _init_data_streaming_notebook(self, root):
        """
        Method to set up a Tkinter notebook with a page for each sensor.
            
        Args - 
            - root: tkinter object, parent for the notebook

        Updates - 
            - self.data_streaming_windows: dict, all tkinter frames in the notebook, can be referenced for plotting, labeling, etc
        """
        # Create a list of pages we want notebook tabs
        self.data_streaming_pages = copy.copy(self.sensor_names)
        self.data_streaming_pages.insert(0, "All")
        
        # Create a tkinter Notebook
        notebook = Notebook(root)
        self.data_streaming_windows = {}
        # For each page we want to stream data for:
        for name in self.data_streaming_pages:
            # 1. Add a frame to the notebook for each sensor
            window = Frame(notebook)
            window.configure(background=self.light_blue)
            window.grid(column=0, row=1, sticky=NSEW)
            notebook.add(window, text=name)
            # 2. And append the frames to a dict so we can access them later
            self.data_streaming_windows.update({name:window})
        # Position the notebook
        notebook.pack(padx=2, pady=1, expand = True)
    
    def _init_data_main_page_fig(self):
        with open("config/main_page_plots.yaml", 'r') as stream:
            self.main_page_plots = yaml.safe_load(stream)

        num_subplots = 0
        y_axis_labels = []
        for key in self.main_page_plots.keys():
            num_subplots += 1
            main_page_plot_titles = self.main_page_plots[key]
            for title in main_page_plot_titles:
                y_axis_labels.append(title)

        fig = plt.figure("All", figsize=(9, 4*num_subplots))
        self.data_streaming_figs.update({"All": fig})
        for i in range(num_subplots):
            ax = fig.add_subplot(num_subplots,1,i+1)
            ax.set_xlabel("Time (epoch)")
            ax.set_ylabel(y_axis_labels[i])

        self.data_streaming_figs.update({"All":fig})

    def _init_data_streaming_figs(self):
        """Method to initialize matplotlib figures and axes for each sensor. These get saved and called later for live plotting
        
            Updates - 
                - self.streaming_data_figs: dict of matplotlib figures"""
        # For each sensor, generate and save a unique matplotlib figure and corresponding axes
        self.data_streaming_figs = {}
        for name in self.sensor_names:
            # We want to make a subplot for each data channel per sensor, so grab those
            channels = list(self.big_data_dict[name]["Data"].keys())
            num_subplots = len(channels)
            # Create a figure and size it based on the number of channels
            fig = plt.figure(name, figsize=(9,4*num_subplots))
            
            # Create a subplot for each channel, and label the axes
            self.data_streaming_figs.update({name:fig})
            _, _, labels = self.get_sensor_data(name)
            for i in range(0, num_subplots):
                ax = fig.add_subplot(num_subplots,1,i+1)
                ax.plot(time.time(), 0)
                ax.set_xlabel("Time (epoch)")
                ax.set_ylabel(labels[i])
                ax.set_xlim([time.time(), time.time()+(5*60)])

            # A little cheesy - futz with the whitespace by adjusting the position of the top edge of the subplots 
            # (as a fraction of the figure height) based on how many subplots we have. For 1 subplot put it at 90% of the figure height, 
            # for 4 subplots put it at 97%, and interpolate between the two otherwise
            plt.subplots_adjust(top=np.interp(num_subplots, [1,4], [0.9,0.97]))

        self._init_data_main_page_fig()

    def _one_canvas(self, f, root, vbar:Scrollbar, row=1, column=0, scroll=True):
        """
        General method to set up a matplotlib embedded canvas in a given root. We're using each canvas
        to hold a matplotlib figure for live plotting
        
        Args - 
            - f: matplotlib figure, to be attached to this canvas
            - root: tkinter object, parent of the canvas
            - vbar: tkinter Scrollbar
            - num_subplots: int, how many subplots we have on this canvas. Used to set the size of the scroll region
        """
        # Initialize and render a matplotlib embedded canvas
        canvas = FigureCanvasTkAgg(f, root)
        canvas.draw()
        # Position the canvas
        canvas.get_tk_widget().grid(row=row, column=column)
        # Make the parent object colored white. For funsies
        root.config(bg=self.dark_blue)
        
        if scroll:
            # Set up the scroll region of the canvas based on the screen size scaled by the number of subplots
            num_subplots = len(f.get_axes())
            scroll_region = num_subplots*self.root.winfo_screenheight() / 2.4 # Magic number! Found that 2.4 was good purely by guess and check
            # Configure the canvas
            canvas.get_tk_widget().config(scrollregion=(0,0,0,scroll_region), # set the size of the scroll region in screen units
                                        yscrollcommand=vbar.set, # link the scrollbar to the canvas
                                        )
            # Set the scrollbar command and position
            vbar.config(command=canvas.get_tk_widget().yview)
            vbar.grid(row=1, column=1, sticky=N+S)
            # Bind the scrollbar to the mousewheel by triggering a callback whenever tkinter registers a <MouseWheel> event
            canvas.get_tk_widget().bind("<MouseWheel>", self._on_mousewheel)
            # Set up the navigation toolbar for the canvas (allows you to pan, zoom, save plots, etc)
            toolbar = NavigationToolbar2Tk(canvas, root, pack_toolbar=False)
            toolbar.grid(row=0, column=0, pady=(10,0))

    def _init_data_streaming_canvases(self):
        """
        Sets up a tkinter canvas for each sensor in its own tkinter frame and with its own embedded matplotlib figure. 
        The frames were set up in _init_data_streaming_notebook(), and the figures in _init_data_streaming_figs(). We pass
        the frame and figure into a canvas (FigureCanvasTkAgg object), set up a scrollbar, and bind the scrollbar to the mousewheel.

        It might not look like anything is getting saved here, but Tkinter handles parent/child relationships internally,
        so the canvases exist wherever Tkinter keeps the frames
        """

        for name in self.data_streaming_pages:
            # Grab the appropriate matplotlib figure and root window (a tkinter frame)
            fig = self.data_streaming_figs[name]
            window = self.data_streaming_windows[name]
            # Make a scrollbar
            vbar = Scrollbar(window, orient=VERTICAL)
            # Make a canvas to hold the figure in the window, and set up the scrollbar
            self._one_canvas(fig, window, vbar)
        
    def _update_plots_1(self):
        
        for name in self.sensor_names:
            fig = self.data_streaming_figs[name]
            axs = fig.get_axes()
            x, ys, channels = self.get_sensor_data(name)

            for i, ax in enumerate(axs):
                (ln,) = ax.get_lines()
                # get copy of entire figure (everything inside fig.bbox) sans animated artist
                # bg = fig.canvas.copy_from_bbox(fig.bbox)
                # draw the animated artist, this uses a cached renderer
                # ax.draw_artist(ln)
                # # show the result to the screen, this pushes the updated RGBA buffer from the
                # # renderer to the GUI framework so you can see it
                # fig.canvas.blit(fig.bbox)

                # # reset the background back in the canvas state, screen unchanged
                # fig.canvas.restore_region(bg)
                # update the artist, neither the canvas state nor the screen have changed
                ln.set_xdata(x)
                ln.set_ydata(ys[i])
                # re-render the artist, updating the canvas state, but not the screen
                ax.draw_artist(ln)
                # copy the image to the GUI state, but screen might not be changed yet
                fig.canvas.blit(fig.bbox)
                # flush any pending GUI events, re-painting the screen if needed
                # fig.canvas.flush_events()
                # you can put a pause in if you want to slow things down
                plt.pause(.1)
    
    def _update_plots(self):
        tstart = time.time()
        """Method that updates the data streaming plots with data stored in self.big_data_dict, should be called as frequently as possible.
        Called in self.run() when the GUI gets updated"""
        # A bunch of loops!
        # 1. Loop through the sensors and grab both their corresponding matplotlib figure/axes and data from their updated buffers
        j = 0

        for name in self.sensor_names:
            fig = self.data_streaming_figs[name]
            axs = fig.get_axes()

            main_page_fig = self.data_streaming_figs["All"]
            axs2 = main_page_fig.get_axes()
            
            x, ys, channels = self.get_sensor_data(name)
            # 2. Loop through the number of data channels present for this sensor (i.e how many deques are present in ys)
            for i, y in enumerate(ys):
                # Finally, plot the updated data...
                axs[i].plot(x, y, '.--')
                # ...and cap the x limits so our plots don't get unreadable as we plot over long timespans.
                xlim = axs[i].get_xlim()
                if (xlim[1] - xlim[0]) >= self.default_plot_length:
                    axs[i].set_xlim([x[-1] - self.default_plot_length, x[-1] + 1]) 

                # # If we also need to plot on the main page, do that here
                # # if name in self.main_page_plots:
                # try: 
                #     if channels[i] in self.main_page_plots[name]:
                #         axs2[j].plot(x, y, '.--')

                #         xlim = axs2[j].get_xlim()
                #         if (xlim[1] - xlim[0]) >= self.default_plot_length:
                #             axs2[j].set_xlim([x[-1] - self.default_plot_length, x[-1] + 1]) 

                #         j+=1
                # except KeyError:
                #     pass
            print(f"buffer length: {len(y)}")

        tend = time.time()
        print(f"updating plots took {tend-tstart} seconds")

    def get_sensor_data(self, sensor_name):
        """
        Method that combs through the data buffer dictionary and pulls out the timestamp and data for each channel corresponding
        to the given sensor_name.

        Args - 
            - sensor_name: str, must match the keys in big_data_dict
        Returns -
            - x_data: list of float, timestamp buffer
            - y_data: list of deque, all the data channels of the given sensor
            - channels: list of str, name of the channel
        """
        # Pull out the timestamp corresponding to the sensor name
        x_data = self.big_data_dict[sensor_name]["Time (epoch)"]
        # Pull out the keys under the "Data" subsection of the sensor to get a list of the channel names
        channels = list(self.big_data_dict[sensor_name]["Data"].keys())
        # For each channel, grab the data and append to a list
        y_data = [self.big_data_dict[sensor_name]["Data"][channel] for channel in channels]

        return x_data, y_data, channels

    def update_buffer(self, new_data:dict, use_noise=False):
        """Method to update the self.big_data_dict buffer with new data from the sensor pipeline. This gets called from executor.py
        
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

    ## --------------------- STATUS GRID --------------------- ##
    
    def _make_sensor_buttons(self, root, sensor_name, row:int, button_rows:int, button_cols:int, button_names, button_callbacks, button_states):
        """Method to make buttons for the status grid cells
        
        Args - 
            - root: tkinter object
            - sensor_name: str, name of the sensor. Should match a key in self.sensor_names
            - row: int, row of the root grid to start the buttons on
            - button_rows: int, how many rows of buttons
            - button_cols: int, how many columns of buttons
            - button_names: list of str, what text we want printed on the buttons
            - button_callbacks: list of methods, callbacks to be assigned to the buttons
            - button_states: list of str, initial status of the button (ACTIVE or DISABLED)
        """
        
        # Loop through the determined number of rows and columns, creating buttons and assigning them callbacks accordingly
        i = 0
        buttons = []
        try:
            for row in range(row, button_rows+row):
                for col in range(button_cols):
                    # The callbacks have been passed in from executor.py, and directly control the sensors. Since I also want to log
                    # the sensor status when the buttons are pushed, wrap up the callback in a functools partial() to give it a little
                    # more functionality. Check out self._sensor_button_callback for more details
                    callback = partial(self._sensor_button_callback, sensor_name, button_callbacks[i])
                    # Create and place the button
                    button = Button(root, text=button_names[i], command=callback, font=self.bold16, state=button_states[i])
                    button.grid(row=row, column=col, sticky=N, padx=10, pady=10)
                    # Grab a hold of the button just in case we want to access it later
                    buttons.append(button)
                    i+=1
        except IndexError as e:
            logger.warning(f"Exception in building status grid buttons: {e}. Your number of buttons probably doesn't divide evenly by {button_rows}, that's fine")

        return buttons
    
    def _make_status_readout(self, root, row, name, col=0, colspan=1):
        """Method to build the sensor status portion of the grid
        
            Args - 
                - root: tkinter object
                - row: int, row of the root grid to position the status readout
                - name: str, which grid cell (and therefore sensor) this status reading corresponds to
                - col: int, column of the root grid to position the sensor readout
                - colspan: int, how many columns of the root grid it should take up
        """
        # We only want to report the status of sensors, not any other grid (like the title), so check if the name
        # we've been given is in our list of sensor names. If it's not, exit
        if name not in self.sensor_names:
            return
        # Make and position a frame at the given column and row - holds the rest of the tkinter objects we're making here
        frame = Frame(root, bg="white")
        frame.grid(column=col, row=row, columnspan=colspan, pady=10, padx=10)
        # Make and position some text
        Label(frame, text="Status:", font=self.bold16, bg="white").grid(column=0, row=0, ipadx=5, ipady=5)
        # Make and position some more text, but hold onto this one - we want to be able to change its color later to 
        # represent sensor status
        status_text = Label(frame, font=self.bold16, bg="white")
        status_text.grid(column=1, row=0, ipadx=5, ipady=5)
        self.sensor_status_colors[name] = status_text

    def _init_sensor_status_dict(self):
        """Method to initialize an empty sensor status dictionary based on the sensors in self.sensor_names,
        will be filled in when a sensor button callback is triggered or self._update_sensor_status is called"""
        self.sensor_status_dict = {}
        self.sensor_status_colors = {}
        for name in self.sensor_names:
            self.sensor_status_dict.update({name:0})
            self.sensor_status_colors.update({name:None})
    
    def _make_status_panel_cell(self, root, title, col, row, button_callbacks, button_names, button_states, font, colspan=1, rowspan=1, color='white'):
        """Method to make one frame of the sensor status panel at the position given with the buttons given

            Args - 
                - root (tkinter object), 
                - title (str, cell title), 
                - col (int, position in root grid), row (int, position in root grid),
                - button_callbacks (list, methods to give the buttons, can be empty), 
                - button_names (list of str, names of the buttons),
                - button_states (list of str, ACTIVE or DISABLED), 
                - colspan (int, column span in root grid), rowspan (int, row span in root grid)
        """  
        # Make a frame at the position we want and make it fill the space (sticky in all directions)
        frame = Frame(root, relief=RAISED, borderwidth=1.25, bg=color, highlightcolor='blue')
        frame.grid(column=col, row=row, columnspan=colspan, rowspan=rowspan, sticky=NSEW)
        # Make it stretchy if the window is resized
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        # If we have more than 4 buttons to put in this cell, split them up into 2 columns and determine how many rows we need
        if len(button_names) >= 4:
            button_rows, button_cols = self._find_grid_dims(num_elements = len(button_names), num_cols=2) 
            title_colspan = 2
        # Otherwise, keep everything in 1 column
        else:
            button_rows, button_cols = self._find_grid_dims(num_elements = len(button_names), num_cols=1) 
            title_colspan = 1
        # Set a title for the cell
        label=Label(frame, text=title, font=font, bg='white')
        label.grid(row=0, column=0, columnspan=title_colspan, sticky=N, pady=20)
        # Make the status readout and sensor control buttons
        self._make_status_readout(frame, 1, title, colspan=title_colspan)
        buttons = self._make_sensor_buttons(frame, title, 2, button_rows, button_cols, button_names, button_callbacks, button_states)
                
        return buttons
    
    def _init_sensor_panel(self, root:Frame):
        """Makes a panel of all the sensors, with buttons to initialize/shutdown sensors, display sensor status, 
        and start/stop data collection.
        
        Args - 
            root: Tkinter frame, parent for the sensor status panel"""
        # Grab the number of rows we should have in our grid given the number of sensors in self.sensor_names 
        # (this is a little unnecessary currently, since I decided one column looked best)
        num_rows, num_cols = self._find_grid_dims(num_elements=len(self.sensor_names), num_cols=1)
        # Make the title row
        title_buttons = self._make_status_panel_cell(root, title="Sensor Status & Control", col=0, row=0, colspan=num_cols, font=self.bold20,
                                                    button_names=["Initialize All Sensors", "Shutdown All Sensors", "Start Data Collection", "Stop Data Collection"],
                                                    button_callbacks=[self._on_sensor_init, self._on_sensor_shutdown, self._on_start_data, self._on_stop_data],
                                                    button_states=[ACTIVE, ACTIVE, DISABLED, DISABLED],
                                                   )
        # Make a list of all buttons that are initially disabled, but should be enabled after sensors have been initialized
        self.buttons_to_enable_after_init = [button for button in title_buttons[2:]]
        # And vice versa with shutdown
        self.buttons_to_disable_after_shutdown = [button for button in title_buttons[2:]]
        # Make all the other rows/cols for the sensors
        i = 0
        try:
            for row in range(2, num_rows+2):
                for col in range(num_cols):
                    # Grab the sensor name
                    sensor_name = self.sensor_names[i]
                    # Grab the button names and callbacks for each sensor (self.button_callback_dict was passed into this GUI when
                    # the object was instantiated, and holds methods for initializing and stopping the sensors)
                    callback_dict = self.button_callback_dict[sensor_name]
                    button_names = list(callback_dict.keys())
                    button_callbacks = list(callback_dict.values())
                    # Make the cell (makes buttons and status indicator)
                    buttons = self._make_status_panel_cell(root, col=col, row=row,
                                                          colspan=num_cols,
                                                          title=sensor_name,
                                                          font=self.bold16,
                                                          button_names=button_names,
                                                          button_callbacks=button_callbacks,
                                                          button_states=[ACTIVE]*len(button_names),
                                                        )
                    i += 1
            # Now that we've made a status grid for each sensor, update them
            self._update_sensor_status()
        except IndexError as e:
            logger.warning(f"Exception in building status grid loop: {e}. Probably your sensors don't divide evenly by {num_cols}, that's fine")

        # Make the grid stretchy if the window is resized, with all the columns and rows stretching by the same weight
        root.columnconfigure(np.arange(num_cols).tolist(), weight=1, minsize=self.grid_width)
        # root.rowconfigure(np.arange(1,num_rows+1).tolist(), weight=1, minsize=self.grid_height) # "+1" for the title row
 
    ## --------------------- LOGGING & NOTETAKING --------------------- ##
    
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
    
    def _config_notes(self):
        """Method to read in the logging/notes configuration yaml file and set up a csv to save manual logs/notes"""
        # Configure the data saving directory and the desired entries for the notes panel
        self._load_notes_directory()
        self._load_notes_entries()
        # Add one more entry for keeping track of the time.time() timestamp
        notes_titles = list(self.notes_dict.keys())
        notes_titles.insert(0, "Internal Timestamp (epoch)")
        # Initialize a csv file to save the notes
        self._init_csv_file(self.notes_filepath, notes_titles)
    
    def _init_notes_panel(self, root):
        """Method to set up a panel with text entry for manual logging and note taking. This gets filled based on
        the log_entries.yaml config file, and saves entries to a notetaking csv (set up in self._config_notes)"""
        # Make a title
        Label(root, text="Notes & Logs", font=self.bold20, bg='white', width=15).grid(column=0, row=0, columnspan=2, sticky=N, pady=10)
        # Grab the elements we want logging entries for (based on the config file)
        entry_text = self.notes_dict.keys()
        self.logging_entries = []
        # For each desired logging entry, try to set up a tkinter Text widget
        try:
            for i, text in enumerate(entry_text):
                # Give the logging entry a title
                Label(root, text=f"{text}:", font=self.bold16, bg='white', width=19, justify=LEFT, anchor=W).grid(column=0, row=i+1, sticky=N+W, padx=(25,5), pady=2.5, ipady=2.5)
                # Set up the text widget
                height = self.notes_dict[text]["entry height"]
                entry = Text(root, font=self.norm16, height=height, width=15)
                entry.grid(column=1, row=i+1, sticky=N+W, padx=(0,15), pady=2.5, ipady=2.5)
                # Hold onto the widget so we can read and clear it later
                self.logging_entries.append(entry)
        
            # Make a Tkinter button with a callback that saves the data entries when presseed
            Button(root, text="LOG", font=self.bold16, bg=self.button_blue, width=15, command=self._on_log).grid(column=0, row=i+3, columnspan=2, pady=30)
            # Make the elements stretchy if the window is resized, with up to 2 columns stretching by the same weight
            root.columnconfigure(np.arange(2).tolist(), weight=1, minsize=self.grid_width)

        # Unless we can't read the dictionary key. In that case, note the error and skip this entry
        except KeyError as e:
            logger.warning(f"Error in reading logging & notes config file: {e}")
        except UnboundLocalError as e:
            logger.warning(f"Error in initializing logging & notes: {e}")
        
    ## --------------------- CALLBACKS --------------------- ##

    def _on_mousewheel(self, event):
        """Method that scrolls the widget that currently has focus, assuming that widget has this callback bound to it"""
        scroll_speed = int(event.delta/120)
        try:
            widget = self.root.focus_get()
            widget.yview_scroll(-1*scroll_speed, "units")
        except Exception as e:
            logger.info(f"Exception in mousewheel callback: {e}")

    def _on_sensor_init(self):
        """Callback for the 'Initialize Sensors' button. Enables the other buttons and tries to call the *sensor init* method
        that was passed into self.button_callback_dict when this class was instantiated. If that method doesn't exist, it lets you know."""
        # Enable other buttons
        for button in self.buttons_to_enable_after_init:
            button["state"] = ACTIVE
        # Try to call the method that's the value of the "All Sensors":"Initialize All Sensors" key of the dictionary
        try:
            self.sensor_status_dict = self.button_callback_dict["All Sensors"]["Initialize All Sensors"]() # <- Oh that looks cursed. This calls the method that lives in the dictionary
        # If that key or method doesn't exist, we likely haven't run this script from executor.py. If we have, check executor._set_gui_buttons()
        except KeyError as e:
            logger.warning(f"Error in reading dictionary: {e}, _on_sensor_init")
        except TypeError as e:
            logger.warning(f"No callback found to initialize sensors. Probably not run from the executor script.")

        self._update_sensor_status()

        print(self.sensor_status_dict)
    
    def _on_sensor_shutdown(self):
        """Callback for the 'Shutdown Sensors' button. Disables the other buttons and tries to call the *sensor shutdown* method
        that was passed into self.button_callback_dict when this class was instantiated. If that method doesn't exist, it lets you know."""
        # Disable other buttons
        for button in self.buttons_to_disable_after_shutdown:
            button["state"] = DISABLED
        # Try to call the method that's the value of the "All Sensors":"Shutdown All Sensors" key of the dictionary
        try:
            self.sensor_status_dict = self.button_callback_dict["All Sensors"]["Shutdown All Sensors"]() # Yep, that again.
        # If that key or method doesn't exist, we likely haven't run this script from executor.py. If we have, check executor._set_gui_buttons()
        except KeyError as e:
            logger.warning(f"Error in reading dictionary: {e}, _on_sensor_shutdown")
        except TypeError as e:
            logger.warning(f"No callback found to shutdown sensors. Probably not run from the executor script.")

        self._update_sensor_status()
    
    def _on_start_data(self):
        """Callback for the 'Start Data Collection' button. Tries to call the *start data collection* method
        that was passed into self.button_callback_dict when this class was instantiated. If that method doesn't exist, it lets you know."""
        # Try to call the method that's the value of the "Data Collection":"Start Data Collection" key of the dictionary
        try:
            self.button_callback_dict["Data Collection"]["Start Data Collection"]()
        # If that key or method doesn't exist, we likely haven't run this script from executor.py. If we have, check executor._set_gui_buttons()
        except KeyError as e:
            logger.warning(f"Error in reading dictionary: {e}, _on_start_data")
        except TypeError as e:
            logger.warning(f"No callback found to start data collection. Probably not run from the executor script.")

    def _on_stop_data(self):
        """Callback for the 'Stop Data Collection' button. Tries to call the *stop data collection* method
        that was passed into self.button_callback_dict when this class was instantiated. If that method doesn't exist, it lets you know."""
        # Try to call the method that's the value of the "Data Collection":"Stop Data Collection" key of the dictionary
        try:
            self.button_callback_dict["Data Collection"]["Stop Data Collection"]()
        # If that key or method doesn't exist, we likely haven't run this script from executor.py. If we have, check executor._set_gui_buttons()
        except KeyError as e:
            logger.warning(f"Error in reading dictionary: {e}, _on_stop_data")
        except TypeError as e:
            logger.warning(f"No callback found to start data collection. Probably not run from the executor script.")

    def _sensor_button_callback(self, button_name, button_command):
        """
        General callback to expand upon the methods we were passed in button_callback_dict when this class was 
        instantiated. It runs the method, then checks to see if it corresponds to a valid sensor. If it does, the 
        method will have returned a status value, so this updates the sensor status accordingly.
        
        Args -
            - button_name (str, should be a key in self.button_callback_dict)
            - button_command (method, should be a value in self.button_callback_dict)
        """
        # Activate the callback. If it's a callback for an individual sensor button (e.g "Start Laser"), the callback will
        # return the status of the sensor. This is either 0 (offline), 1 (online and initialized), 2 (disconnected/simulated hardware)
        status = button_command()
        # We only want to do something with that result if it is actually an individual sensor button, so check for that here
        if button_name in self.sensor_names:
            # Update the dictionary that holds sensor status and reflect that change in the GUI
            self.sensor_status_dict[button_name] = status
            self._update_sensor_status()

    def _on_log(self):
        """Callback for the 'log' button (self.init_logging_panel), logs the text entries (self.logging_entries) to a csv"""
        # Loops through the elements in self.logging_entries (tkinter Text objects), reads and clears each element
        timestamp = time.time()
        notes = [timestamp]
        for entry in self.logging_entries:
            # Makes sure we're only working with tkinter Text objects, and also conveniently
            # tells VSCode the type of the list element
            if type(entry) == Text:
                # Get everything (from the first to last index) and strip away any white space
                notes.append(entry.get('1.0', 'end').strip())
                # Clear the text object
                entry.delete('1.0', 'end')
        # Dump all the text entries to the notes csv we set up earlier
        self._save_data_notes(notes)
    
    ##  --------------------- HELPER FUNCTIONS --------------------- ##

    def toggle_button(self, button: Button):
        """Method that toggles a button between its 'normal' state and its 'disabled' state"""
        if button["state"] == NORMAL:
            button["state"] = DISABLED
        else:
            button["state"] = NORMAL
    
    def _find_grid_dims(self, num_elements, num_cols):
        """Method to determine the number of rows we need in a grid given the number of elements and the number of columns
        
            Returns - num_rows (int), num_cols (int)"""

        num_rows = num_elements / num_cols
        # If the last number of the fraction is a 5, add 0.1. This is necessary because Python defaults to 
        # "bankers rounding" (rounds 2.5 down to 2, for example) so would otherwise give us too few rows
        if str(num_rows).split('.')[-1] == '5':
            num_rows += 0.1
        num_rows = round(num_rows)

        return num_rows, num_cols
    
    def _update_sensor_status(self):
        """Method to update the sensor status upon initialization or shutdown. Uses the values stored in
        self.sensor_status_dict to set the color and text of each sensor status widget."""
        # Loop through the sensors and grab their status from the sensor status dictionary
        for name in self.sensor_names:
            status = self.sensor_status_dict[name]
            # If we're offline / failed initialization
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
            elif status == 3:
                color = "#D55E00"
                text = "ERROR"
                
            # If we recieved an erroneous reading, make it obvious
            else:
                color = "purple"
                text = "?????"

            # Update the sensor status accordingly
            label = self.sensor_status_colors[name] # This is a dictionary of tkinter objects
            label["bg"] = color
            label["text"] = text
    
    def _save_data_notes(self, notes):
        """Method to save the logged notes to a csv file"""
        # Check if a file exists at the given path and write the notes
        try:
            with open(self.notes_filepath, 'a') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', lineterminator='\r')
                writer.writerow(notes)
        # If it doesn't, something went wrong with initialization - remake it here
        except FileNotFoundError:
            with open(self.notes_filepath, 'x') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                notes_titles = list(self.notes_dict.keys())
                notes_titles.insert(0, "Internal Timestamp (epoch)")
                writer.writerow(notes_titles) # give it a title
                writer.writerow(notes) # write the notes

    def _init_csv_file(self, filepath, header):
        # Check if we can read the file
        try:
            with open(filepath, 'r'):
                pass
        # If the file doesn't exist, create it and write in whatever we've passed as row titles
        except FileNotFoundError:
            with open(filepath, 'x') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', lineterminator='\r')
                writer.writerow(header)
    
    ##  --------------------- EXECUTABLES --------------------- ##
    
    def run_cont(self):
        self.root.mainloop()
        self.root.destroy()

    def run(self, delay):
        # self._update_plots()
        try:
            tstart = time.time()
            self.root.update()
            self.root.after(50, self._update_plots)
            tend = time.time()
            print(f"updating tkinter took {tend-tstart} seconds")
            time.sleep(delay)
            return True
        except:
            return False


if __name__ == "__main__":
    # Read the sensor data config file in order to grab the sensor names
    with open("config/sensor_data.yaml", 'r') as stream:
        big_data_dict = yaml.safe_load(stream)
    sensor_names = big_data_dict.keys()

    # Read in an instance of the sensor class to grab the callback methods
    from main_pipeline.sensor import Sensor
    sensor = Sensor()

    # Initialize an empty dictionary to hold the methods we're going to use as button callbacks. Sometimes
    # these don't exist (e.g the Picarro doesn't have start/stop, only query), so initialize them to None
    button_dict = {}
    for name in sensor_names:
        button_dict.update({name:{}})

    # Add the start/stop measurement methods for the Abakus and the Laser Distance Sensor
    button_dict["Abakus Particle Counter"] = {"Start Abakus": sensor.abakus.initialize_abakus,
                                              "Stop Abakus": sensor.abakus.stop_measurement}

    button_dict["Laser Distance Sensor"] = {"Start Laser": sensor.laser.initialize_laser,
                                            "Stop Laser": sensor.laser.stop_laser}
    
    button_dict["Flowmeter"] = {"Start SLI2000": sensor.flowmeter_sli2000.initialize_flowmeter,
                                "Start SLS1500": sensor.flowmeter_sls1500.initialize_flowmeter}
    
    # Finally, add a few general elements to the dictionary - one for initializing all sensors (self._init_sensors), 
    # one for starting (self._start_data_collection) and stopping (self._stop_data_collection) data collection 
    # and one for shutting down all sensors (self._clean_sensor_shutdown)
    button_dict.update({"All Sensors":{"Initialize All Sensors":None, "Shutdown All Sensors":None}})
    button_dict.update({"Data Collection":{"Start Data Collection":None, "Stop Data Collection":None}})
    
    app = GUI(sensor_button_callback_dict=button_dict)

    running = True
    while running:
        running = app.run(0.1)
