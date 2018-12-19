#!/usr/bin/python3
#
################################################
# Package for communication with SPORTident HW
#
# Author:  Martin Horak
# Version: 1.1
# Date:    9. 12. 2018
#
################################################

# Communication constants
WAKE = 0xff;
STX = 0x02;
ETX = 0x03;
ACK = 0x06;
NAK = 0x15;
DLE = 0x10;

SI_VENDOR_ID = '10c4'
SI_PRODUCT_ID = '800a'

import os, logging

##################################
# Custom exceptions
##################################
class DataCrcError(Exception):
    pass

class DataReadError(Exception):
    pass

class HandshakeMaxTries(Exception):
    pass

##################################
# SI lowlevel functions
##################################

#--------------------------------#
def crc_l(length, data):
    """CRC computation."""
    Polynom = 0x8005;
    Bitmask = 0x8000;
    Intmask = 0xFFFF;

    p = 0
    if length < 2: return 0
    sum0 = data[p]
    p += 1
    sum0 = (sum0 << 8) + data[p]
    p += 1

    if length == 2: return sum0

    i = length >> 1
    while i > 0:
        if i > 1:
            sum1 = data[p]
            p += 1
            sum1 = ((sum1 << 8) & Intmask) + data[p]
            p += 1
        else:
            if length & 1:
                sum1 = data[p] << 8
                p += 1
            else:
                sum1 = 0

        for k in range(0,16):
            if sum0 & Bitmask:
                sum0 = (sum0 << 1) & Intmask
                if sum1 & Bitmask: sum0 = sum0 + 1 & Intmask
                sum0 ^= Polynom
            else:
                sum0 = (sum0 << 1) & Intmask
                if sum1 & Bitmask: sum0 = sum0 + 1 & Intmask
            sum1 = (sum1 << 1) & Intmask
        i -= 1
    return sum0

#--------------------------------#
def crc(data):
    """CRC computation of all data (length calculated)."""
    length = len(data)
    return si_crc_l(length, data)

#--------------------------------#
def station_detect():
    """Detect device of connected SI master station."""
    devices = []

    for root, dirs, files in os.walk('/sys/devices'):
        if os.path.basename(root).startswith('ttyUSB'):
            idroot = os.path.dirname(os.path.dirname(root))   # Two levels up
            if os.path.isfile(idroot+"/idVendor") and os.path.isfile(idroot+"/idProduct"):
                with open(idroot+"/idVendor") as f:
                    vendor = f.read().replace('\n', '')
                with open(idroot+"/idProduct") as f:
                    product = f.read().replace('\n', '')
                if vendor == SI_VENDOR_ID and product == SI_PRODUCT_ID:
                    devices.append(os.path.basename(root))
    return devices

#--------------------------------#
def ttysetup(port, baud=38400, timeout=20):
    tty = serial.Serial(port, baud, timeout=timeout)
    return tty

#--------------------------------#
def frame(command, data):
    """Add framing to output data."""
    length = len(data)
    data[:0] = (command, length)
    crcsum = crc(data);
    data[:0] = (WAKE, STX)
    data.extend((crcsum >> 8, crcsum & 0xff, ETX))
    return bytearray(data)

#--------------------------------#
def unframe(data):
    """Strip framing from input data."""
    i = 0
    while data[i] != STX:
        if data[i] == NAK: return NAK, ()
        if data[i] == ACK: return ACK, ()
        i += 1
        if i >= len(data): raise DataReadError()
    i += 1
    command = data[i]
    i += 1
    length = data[i]
    i += 1
    data_crc = data[i+length] << 8 + data[i+length+1]
    comp_crc = crc_l(length, data[i:])
    if(data_crc != comp_crc): raise DataCrcError()
    return command, list(data[i+2:])

#--------------------------------#
def siread(tty):
    """Read data from SI station."""
    data = tty.read(SI_CHUNK)
    if data: logging.debug("<i<<< " + ':'.join('{:02x}'.format(x) for x in data)
    return data

#--------------------------------#
def siwrite(tty, command, data=[]):
    """Write data to SI station."""
    fdata = frame(command, data)
    tty.write(fdata)
    logging.debug(">o>>> " + ':'.join('{:02x}'.format(x) for x in fdata)
    return

#--------------------------------#
def handshake(tty, tries, command, data=[]):
    """Try write - read cycle tries times."""
    while tries > 0:
        siwrite(tty, command, data)
        data = siread(tty)
        if data:
            status, udata = unframe(data)
            if status != NAK: return udata
        tries -= 1
        time.sleep(1)
    raise HandshakeMaxTries()    

def siinit(device):
    """Initialize serial communication with SI master station."""
    bauds = (38400, 4800)
    for baudrate in bauds:
        tty = serial.Serial(device, baudrate, timeout=2)
        try:
            handshake(tty, 1, 0xf0, 0x4d)
        except HandshakeMaxTries:
            tty.close()
        else:
            break

