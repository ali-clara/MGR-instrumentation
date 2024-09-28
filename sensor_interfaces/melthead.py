import serial
from serial import SerialException
import time
import yaml

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
    def __init__(self, serial_port="COM7", baudrate=38400) -> None:
        self.initialize_pyserial(serial_port, baudrate)

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
    
    def initialize_pid(self):
        pass
    
    def query(self):
        pass

    def _calc_header_crc(self):
        crc =   [0x00, 0xfe, 0xff, 0x01, 0xfd, 0x03, 0x02, 0xfc,
                0xf9, 0x07, 0x06, 0xf8, 0x04, 0xfa, 0xfb, 0x05,
                0xf1, 0x0f, 0x0e, 0xf0, 0x0c, 0xf2, 0xf3, 0x0d,
                0x08, 0xf6, 0xf7, 0x09, 0xf5, 0x0b, 0x0a, 0xf4,
                0xe1, 0x1f, 0x1e, 0xe0, 0x1c, 0xe2, 0xe3, 0x1d,
                0x18, 0xe6, 0xe7, 0x19, 0xe5, 0x1b, 0x1a, 0xe4,
                0x10, 0xee, 0xef, 0x11, 0xed, 0x13, 0x12, 0xec,
                0xe9, 0x17, 0x16, 0xe8, 0x14, 0xea, 0xeb, 0x15,
                0xc1, 0x3f, 0x3e, 0xc0, 0x3c, 0xc2, 0xc3, 0x3d,
                0x38, 0xc6, 0xc7, 0x39, 0xc5, 0x3b, 0x3a, 0xc4,
                0x30, 0xce, 0xcf, 0x31, 0xcd, 0x33, 0x32, 0xcc,
                0xc9, 0x37, 0x36, 0xc8, 0x34, 0xca, 0xcb, 0x35,
                0x20, 0xde, 0xdf, 0x21, 0xdd, 0x23, 0x22, 0xdc,
                0xd9, 0x27, 0x26, 0xd8, 0x24, 0xda, 0xdb, 0x25,
                0xd1, 0x2f, 0x2e, 0xd0, 0x2c, 0xd2, 0xd3, 0x2d,
                0x28, 0xd6, 0xd7, 0x29, 0xd5, 0x2b, 0x2a, 0xd4,
                0x81, 0x7f, 0x7e, 0x80, 0x7c, 0x82, 0x83, 0x7d,
                0x78, 0x86, 0x87, 0x79, 0x85, 0x7b, 0x7a, 0x84,
                0x70, 0x8e, 0x8f, 0x71, 0x8d, 0x73, 0x72, 0x8c,
                0x89, 0x77, 0x76, 0x88, 0x74, 0x8a, 0x8b, 0x75,
                0x60, 0x9e, 0x9f, 0x61, 0x9d, 0x63, 0x62, 0x9c,
                0x99, 0x67, 0x66, 0x98, 0x64, 0x9a, 0x9b, 0x65,
                0x91, 0x6f, 0x6e, 0x90, 0x6c, 0x92, 0x93, 0x6d,
                0x68, 0x96, 0x97, 0x69, 0x95, 0x6b, 0x6a, 0x94,
                0x40, 0xbe, 0xbf, 0x41, 0xbd, 0x43, 0x42, 0xbc,
                0xb9, 0x47, 0x46, 0xb8, 0x44, 0xba, 0xbb, 0x45,
                0xb1, 0x4f, 0x4e, 0xb0, 0x4c, 0xb2, 0xb3, 0x4d,
                0x48, 0xb6, 0xb7, 0x49, 0xb5, 0x4b, 0x4a, 0xb4,
                0xa1, 0x5f, 0x5e, 0xa0, 0x5c, 0xa2, 0xa3, 0x5d,
                0x58, 0xa6, 0xa7, 0x59, 0xa5, 0x5b, 0x5a, 0xa4,
                0x50, 0xae, 0xaf, 0x51, 0xad, 0x53, 0x52, 0xac,
                0xa9, 0x57, 0x56, 0xa8, 0x54, 0xaa, 0xab, 0x55
                ]

        b = bytes.fromhex('55 FF 05 10 00 00 0A')
        print(b)

        print(b[:6])

        print(~crc[b[6] ^ crc[b[5] ^ crc[b[4] ^ crc[b[3] ^ crc[~b[2]]]]]])
    
    def send_setpoint(self, setpoint=None):
        preamble = '55 FF' 
        frame_type = '05'
        destination_address = '10' 
        source_address = '00' 
        length = '00 0A'
        header_crc = 'EC'

        cmd = bytes.fromhex("55 FF 05 10 00 00 0A EC 01 04 07 01 01 08 42 00 00 00 AB 02") # 0, should be 32
        self.ser.flush()
        self.ser.write(cmd)

    def start_control_loop(self):
        # print(self.melthead_on)
        # if not self.melthead_on:
        self.ser.write(self.AUTO)
        self.melthead_on = True

    def stop_control_loop(self):
        # if self.melthead_on:
        self.ser.write(self.OFF)
        self.melthead_on = False

if __name__ == "__main__":

    ## ------- UI INTEFACE FOR TESTING  ------- ##
    with open("config/sensor_comms.yaml", 'r') as stream:
        comms_config = yaml.safe_load(stream)

    port = comms_config["Melthead"]["serial port"]
    baud = comms_config["Melthead"]["baud rate"]

    mymelt = MeltHead(serial_port=port, baudrate=baud)
    # mymelt._calc_header_crc()
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
            mymelt.send_setpoint()
        elif command == "x" or command == "X":
            stop = True
        else:
            print("Invalid entry. Try again")

# cmd = b'\x01\x03\x01\x68\x00\x02\x44\x2B'

# cmd = bytes.fromhex('55 FF 05 10 00 00 06 E8 01 03 01 04 01 01 E3 99')

# cmd = bytes.fromhex('55 FF 05 10 00 00 0A EC 01 04 07 01 01 08 3F 80 00 00 8D DF') # -17.2, should be 1

# cmd = bytes.fromhex("55 FF 05 10 00 00 0A EC 01 04 07 01 01 08 C1 89 99 9A 6C 6F" ) # -27.3, should be -17.2

# cmd = bytes.fromhex("55 FF 05 10 00 00 0A EC 01 04 07 01 01 08 41 20 00 00 5D 24") # -12.2, should be 10

# cmd = bytes.fromhex("55 FF 05 10 00 00 0A EC 01 04 07 01 01 08 41 A0 00 00 B1 28") # -6.7, should be 20

# cmd = bytes.fromhex("55FF 0510 0000 0AEC 0104 0701 0108 41F0 0000 52AB") # -1.1, should be 30

# cmd = bytes.fromhex("55 FF 05 10 00 00 0A EC 01 04 07 01 01 08 42 00 00 00 AB 02") # 0, should be 32 ### OH SHIT IT'S CELSIUS

# cmd = bytes.fromhex(" 55 FF        05             10                00           00 0A                 EC      01 04     07 01      01 08   42 0C 00 00         08 A7")             # 1.7, should be 35
#                     |preamble|Frame type (?)|dest. addr (zone)|source addr.|length (MSB first)(10)|header crc|        ^parameter^           ^ iEEE 754 ^   |data crc (LSB first)|   
#                                  
#                       BACnet Data Expecting Reply?
#                        
# cmd = bytes.fromhex("55 FF    05  10   00 00 0A EC 01 04 07 01 01 08 42 20 00 00 90 01") # 4.4, should be 40

# cmd = bytes.fromhex("55FF 0510 0000 0AEC 0104 07 01 01 08 42 48 00 00 1F C2") # 10, should be 50

# cmd = bytes.fromhex("55FF 0510 0000 06E8 0103 0107 0101 8776")

# cmd = bytes.fromhex("55 FF 05 10 03 00 06 43 01 03 02 08 1F 01 0C 16")

# myserial = serial.Serial(port="COM7", baudrate=38400, timeout=1)

# res_list = []
# for i in range(1):
#     myserial.flush()
#     myserial.write(cmd)
#     res = myserial.readline()
#     # res = read_temp()
#     # print(res)
#     res_str = [str(res.hex())]
#     # print([res_str[i:i+2] for i in range(0, len(res_str), 2)])
#     res_list.append(res_str)
#     # time.sleep(1)

# print(res_list)

# myserial.close()

