import struct
import numpy as np

def from_bytes(b):
    return struct.unpack('!f', b)[0]

def dec_from_hex(h):
    """
        Function to convert a hexadecimal string (e.g what is returned from the Bronkhorst) into an IEEE floating point. It's
        somewhat incomprehensible here, I pulled it from stack overflow - https://stackoverflow.com/questions/51179116/ieee-754-python
         
        The actual math that's happening behind the scenes gets discussed here:
        https://www.mimosa.org/ieee-floating-point-format/ and https://www.h-schmidt.net/FloatConverter/IEEE754.html
        
        In short, the IEEE 754 standard formats a floating point as N = 1.F x 2E-127, 
        where N = floating point number, F = fractional part in binary notation, E = exponent in bias 127 representation.

        The hex input corresponds to a 32 bit binary:
                Sign | Exponent  |  Fractional parts of number
                0    | 00000000  |  00000000000000000000000
            Bit: 31   | [30 - 23] |  [22        -         0]

        Args:
            h (str, hexadecimal representation of binary string)

        Returns:
            (float, number in decimal notation)
        """
    return from_bytes(bytes.fromhex(h))

def from_bin(b):
    return struct.unpack('!f', int(b, 2).to_bytes(4, byteorder='big'))[0]

def to_bytes(f):
    return struct.pack('!f', f)

def dec_to_hex(f):
    """Same logic as dec_to_hex, but the other way around."""
    return to_bytes(f).hex()

def to_bin(f):
    return '{:032b}'.format(struct.unpack('>I', struct.pack('!f', f))[0])

if __name__ == "__main__":
    # Make sure it's working as we expect - these return errors if they're false, and nothing if they're true
    assert dec_from_hex('c4725c44') == -969.441650390625
    assert from_bin('11000100011100100101110001000100') == -969.441650390625
    assert from_bytes(b'\xc4r\\D') == -969.441650390625
    assert dec_to_hex(-969.441650390625) == 'c4725c44'
    assert to_bin(-969.441650390625) == '11000100011100100101110001000100'
    assert to_bytes(-969.441650390625) == b'\xc4r\\D'

    # For a more visual test of what's going on, make sure that converting to hex and back again 
    # produces the same output for a variety of numbers
    test_list = np.linspace(-10, 10, 47) # 47 numbers in fact, between -10 and 10
    print("Starting numbers")
    print(test_list)

    result_list = []
    for num in test_list:
        hex_rep = dec_to_hex(num)
        dec_rep = dec_from_hex(hex_rep)
        # If we're off by more than 0.001, throw an error
        assert np.isclose(num, dec_rep, atol=0.001)
        result_list.append(dec_rep)
    
    print("Those numbers converted to IEEE754 hex representation and back again")
    print(np.array(result_list))
