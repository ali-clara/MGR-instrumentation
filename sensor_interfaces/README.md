# Sensor Interfaces

## Current Sensors
Here is a list of the sensors currently integrated into this framework and a brief description of the data they return. For their [user manuals](../doc/instrument-manuals/), see `doc/instrument-manuals`.

### Abakus
- Particle counter
- [Website](https://www.fa-klotz.de/particlecounters/liquids/products-particle-counter-liquids/11-particle-counter-liquids-abakus-mobil-touch.php)
- [User Manual](../doc/instrument-manuals/Abakus_manual.pdf)
- Required drivers: None
- Out-of-box software: Log & Show. Doesn't seem to be downloadable, but might exist on a CD somewhere in the lab
- Communicates with: Serial (baud rate 38400)
- Sensor output: string of *bins* and *counts*. The Abakus has 32 bins, each corresponding to a different particle size. It provides the bin label and the counts of each bin.

### Picarro Gas Analyzer
- Spectrograph used to measure the concentrations of different gasses. Currently measures CH4, CO2, H2O, and CO
- [Website](https://www.picarro.com/environmental/products/g2401_gas_concentration_analyzer)
- [User manual](../doc/instrument-manuals/Picarro/G2401-UserManual-40010-Rev_F.pdf)
- [Programming guide](../doc/instrument-manuals/Picarro/40-0063%20Rev%20A_RemoteInterfaceProgrammingGuide%20(3).pdf)
- Required drivers: None
- Out-of-box software: On the Picarro itself
- Communicates with: Serial (baud rate 19200)
    - Set up communication on the Picarro through the Desktop folder Picarro Utilities > Setup Tool. This launches an app that allows Serial/TCP communication, as well as some other data management functionality.
    - Under **Port Manager**, our Picarro has **Command Interface** set to **COM2**.
- Sensor output: string of gas concentrations

### Sensirion flow meters
- Two liquid flow meters that measure water flow
- Website: [SLI2000](https://sensirion.com/products/catalog/SLI-2000) and [SLS1500](https://sensirion.com/products/catalog/SLS-1500)
- Required drivers: None
- Out-of-box software: [USB RS485 Sensor Viewer](https://sensirion.com/products/downloads?category=7&topic=5)
- Communicates with: Serial (baud rate 115200)
- Sensor output: bytestring. The flow meters have the most complicated data processing, as their output includes validation bits and must be further validated with a checksum. Check out that interface for more info.

### Dimetix laser
- Laser distance sensor used to measure the ice core. Also has a temperature reading.
- [Website](https://dimetix.com/en/?product=d-series)
- [User manual](../doc/instrument-manuals/LaserDistance_TechnicalReferenceManual_DSeries_V114-1.pdf)
- Required drivers: None
- Out of box software: None
- Communicates with: Serial (baud rate 19200)
- Sensor output: string with either temperature or distance in 0.1cm or 0.1C

### Bronkhorst
- Pressure sensor and controller
- [Website](https://www.bronkhorst.com/en-us/products-en/pressure/iq-flow/?page=1#)
- [User manual](../doc/instrument-manuals/Bronkhorst/917045-Manual-IQ-FLOW.pdf)
- [Programming guide](../doc/instrument-manuals/Bronkhorst/917027-Manual-RS232-interface.pdf)
- Required drivers: None
- Out of box software: There are [several](https://www.bronkhorst.com/en-us/products-en/accessories-and-software/flowware/), I used [FlowDDE](https://www.bronkhorst.com/en-us/products-en/accessories-and-software/flowware/flowdde/) to verify comms
- Communicates with: Serial (baud rate 38400)
- Sensor output: depends on the query, returns strings of hex pairs that correspond to both command returns and data

### Melthead (aka Watlow EZ-Zone PID Controller)
- PID Controller
- [Website](https://www.watlow.com/Products/Controllers/Temperature-and-Process-Controllers/EZ-ZONE-PM-Controller) - our model is discontinued
- [User manual](../doc/instrument-manuals/Melthead/EZ-ZonePMManual%20rev%20J.pdf)
- Required drivers: [USB Drivers](https://www.advantech.com/en-us/support/details/driver?id=1-HIPU-30) for the BB-485 serial -> usb converter
- Out of box software: [EZ-ZONE Configurator v6.1](https://www.watlow.com/Resources-and-Support/Technical-Library/Software-and-Demos?keyw=configurator)
- Communicates with: Serial (baud rate 38400) (sortof)
    - This one's a doozy! Per it's documentation, any model numbers of the form `PM _ _ _ _ _ - A _ _ _ _ _ _` don't support any external communications options. Our model number is `PM _ _ _ _ _ - AAAAAA`.
<img src="../doc/imgs/watlow-manual-comms-options.png">
    - However, it does say that *Standard Bus EIA-485* is included for all models, so I went deep down a rabbit hole trying to figure out how it uses standard serial communication. There's no documentation, but by using the Configurator software and monitoring the commands sent back and forth (I used [Free Serial Analyzer](https://freeserialanalyzer.com/), but other methods work too!) I was able to piece together some of the comms.
- I can **send a temperature setpoint** and **start/stop the control loop**. Unfortunately, I was unable to decipher the returned messages so can't read the device temperature.
- The device has a number of channels you can view, either by cycling through with the buttons or by looking at the configurator software. There are too many to list here (more info in [this master doc](../doc/instrument-manuals/Melthead/Master%20PM%20Command%20Definitions.pdf)), but the following describes how to display the most important parameters on the PID module
    - Hold down the two grey up/down buttons for ~3 seconds, until the device reads `AI, oPEr`. You're now in Operation mode, parameter Analog Input. 
    - Repeatedly press the grey `∨` button until the device reads `MON` - Monitor mode. 
    - Press the blue button with circular arrows `⟳` to enter this menu. The device will read `1`
    - Press `⟳` again to enter the Monitor 1 channel. Now you can cycle through different device information with `⟳`. 
    - This displays the control loop mode (`Off` or `Auto`), the heater percentage `(0-100%)`, the setpoint (`X.X`, deg C), and the current analog reading (`X.X`, deg C)
    - To exit any menu, press the grey `∞` button.
    
## Simulated Instruments
The file `simulated_instruments.py` allows us to use shadow hardware, which is a fancy way of saying it lets us run the main sensor-interpreter-writer pipeline if we're not connected to real sensors. 

Each independent sensor interface class is replicated in this file. By creating classes with the same name and that have the same functions/methods, we can import "sensors" into steps further along the pipeline without errors. These classes and methods don't do anything much, but they're really useful for debugging the rest of the pipeline offline.

<style>
    .highlight {
        color: black;
        background-color: #FFC107;
    }
</style>

- <span class="highlight">Important note:</span> **debug mode.** Near the top of `simulated_instruments.py` is a boolean "debug" flag. **Unless you have a good reason, this flag should always be False**. If True, the "sensors" in `simulated_instruments` report fake data in the expected format - this is important for debugging and testing pipeline/GUI capabilities, but runs the risk of introducing fake data into your experiments if sim hardware is active. If the flag is False, the "sensors" report NAN.
- At the highest level, this flag gets set in `gui.py -> init_data_pipeline()`


## Adding a New Sensor
This package was built with modularity in mind, so adding new sensors should be relatively straightforward. Here are the files to modify and how to modify them.

Key: **Class methods**, *Class Names*, `Files and Directories`


- `config/sensor_comms.yaml` 
    - Add a new entry with the name of the sensor and any information needed to communicate with the sensor, such as serial port and baud rate. The spelling here isn't critical, as long as you match it when you load the configuration file in `sensor.py`.
- `config/sensor_data.yaml`
    - Add a new entry with the name of the sensor and (at least) two keys: "Time (epoch)" and "Data". Under "Data", add the names of different data streams / channels you plan to gather from this sensor.
- `sensor_interfaces/`
    - In this directory, make a new file (e.g. `my_new_sensor_name.py`) to communicate with the sensor. Set it up as a class (e.g. *MySensor*) with different methods for initializing, querying, shutting down, etc. I can't help you much with this since it's pretty sensor specific, but hopefully the existing sensor interface files help.
- `sensor_interfaces/sim_instruments.py`
    - In this file, make another *MySensor* class with methods that mirror the ones you just created in `my_new_sensor_name.py`. They can have as many or as few capabilities as you like (e.g they can all just be "pass", that's totally fine), but this allows the entire pipeline to run even when the sensor is unplugged.
- `main_pipeline/sensor.py`
    - Directly under the imports, add a try-except block for your new sensor. It should try to set up a connection with the specifications you set in `sensor_comms.py`. If it's able to do this, it imports the real sensor class from `sensor_interfaces`. If it's unable to do this, it imports the fake sensor class from `sim_instruments`.
    - In **init**, instantiate the *MySensor* class and save it to a class variable.
    - In **initialize_sensors**, call the *MySensor* initialization function and add the result to the sensor status dictionary
    - If *MySensor* has a shutdown function, add it to **shutdown_sensors** add the result to the sensor status dictionary
    - Make a producer method for your new sensor (**my_new_sensor_producer**), which gets the most recent raw data (probably from a "query" method in *MySensor*) and writes it to a bus.
- `main_pipeline/interpreter.py`
    - Make a new method to process raw the data returned from querying the sensor, e.g **process_my_new_sensor_data**. This will process whatever was written to the Bus in **my_new_sensor_producer**, and is highly sensor dependent. It must also add the processed data to the big_dict file, which was created with the keys set in `config/sensor_data.yaml`.
    - In **main_consumer_producer**, add a function argument "my_new_sensor_bus:Bus". Then, add lines to read the bus and pass that data into your new sensor processing function.
- `GUI.py` - Adding in data streaming is automatic with external configuration files, but adding control requires some modification of source code.
    - In **define_sensor_button_callbacks**, add a dictionary entry to sensor_buttons for any control buttons you want on the GUI. These will call the instance of MySensor that exists in the *Sensor* class, and can call whatever methods are available there (e.g self.sensor.mysensor.initialize_mysensor).
    - In **init_data_pipeline**, add a bus for your new sensor (self.my_sensor_bus)
    - In **_thread_data_collection**, add your new sensor to the data processing pipeline. 
        - Submit **my_new_sensor_producer** to the executor with self.my_sensor_bus as its argument. 
        - Add self.my_sensor_bus as an argument to the already-submitted **main_consumer_producer** method in the same position you set in `main_pipeline/interpreter.py`
