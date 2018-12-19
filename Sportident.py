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

NOSTX  = 0xa0;
NODATA = 0xa1;
BADCRC = 0xa2;
OK     = 0x00;

MAXTRIES = 5

SI_VENDOR_ID = '10c4'
SI_PRODUCT_ID = '800a'

# Commands
CMD_SETMSMODE = 0xf0; # mode
CMD_SETTIME   = 0xf6; # p1..p7
CMD_GETTIME   = 0xf7;
CMD_OFF       = 0xf8;
CMD_BEEP      = 0xf9; # numbeeps
CMD_SETSPEED  = 0xfe; # speed
CMD_GETMEM    = 0x81; # adr2, adr1, adr0, numbytes
CMD_CLEARMEM  = 0xf5;
CMD_SETDATA   = 0x82; # offset, [data]
CMD_GETDATA   = 0x83; # offset, numbytes
CMD_GETSI5    = 0xb1;
CMD_GETSI6    = 0xe1; # bn
CMD_GETSI8    = 0xef; # bn

# Autosend commands
CMD_INSI5     = 0xe5; # cn1, cn0, si3..si0
CMD_INSI6     = 0xe6; # cn1, cn0, si3..si0
CMD_INSI8     = 0xe8; # cn1, cn0, si3..si0
CMD_OUTSI     = 0xe7; # cn1, cn0, si3..si0
CMD_PUNCH     = 0xd3; # cn1, cn0, si3..si0, td, th, tl, tss, mem2..mem0

# Arguments
MODE_LOCAL = 0x4d;
MODE_REMOTE = 0x53;
SPEED_38400 = 0x01;
SPEED_4800  = 0x00;

# Offsets           # Len
O_MODE      = 0x71; # 1
O_CODE      = 0x72; # 2
O_PROT      = 0x74; # 1


import os, logging

##################################
# Custom exceptions
##################################
class DataError(Exception):
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
# Deprecated --------------------#
def frame(command, data):
    """Add framing to output data."""
    length = len(data)
    data[:0] = (command, length)
    crcsum = crc(data);
    data[:0] = (WAKE, STX)
    data.extend((crcsum >> 8, crcsum & 0xff, ETX))
    return bytearray(data)

#--------------------------------#
# Deprecated --------------------#
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
    if data:
        logging.debug("<i<<< " + ':'.join('{:02x}'.format(x) for x in data)
        i = 0
        while data[i] != STX:
            if data[i] == NAK: return NAK, ()
            if data[i] == ACK: return OK, ()
            i += 1
            if i >= len(data): return NOSTX, ()
        i += 1
        command = data[i]
        i += 1
        length = data[i]
        i += 1
        data_crc = data[i+length] << 8 + data[i+length+1]
        comp_crc = crc_l(length, data[i:])
        if(data_crc != comp_crc): return BADCRC, ()
        ret = list(data[i:])
        ret.insert(0, command)
        return OK, ret
    return NODATA, ()

#--------------------------------#
def siwrite(tty, command, data=[]):
    """Write data to SI station."""
    length = len(data)
    data[:0] = (command, length)
    crcsum = crc(data);
    data[:0] = (WAKE, STX)
    data.extend((crcsum >> 8, crcsum & 0xff, ETX))
    logging.debug(">o>>> " + ':'.join('{:02x}'.format(x) for x in fdata)
    tty.write(bytes(data))
    return

#--------------------------------#
def handshake(tty, command, data=[], tries=MAXTRIES):
    """Try write - read cycle tries times."""
    while tries > 0:
        siwrite(tty, command, data)
        status, data = siread(tty)
        if status == OK:
            return data
        tries -= 1
        time.sleep(1)
    raise HandshakeMaxTries()    

def siinit(device):
    """Initialize serial communication with SI master station."""
    bauds = (38400, 4800)
    for baudrate in bauds:
        tty = serial.Serial(device, baudrate, timeout=2)
        try:
            data = handshake(tty, CMD_SETMSMODE, [MODE_LOCAL], 3)
        except HandshakeMaxTries:
            tty.close()
        else:
            masters[device]['speed'] = baudrate
            break
    else:
        return False

    masters[device]['cn'] = (data[1] << 8) | data[2]
    data = handshake(tty, CMD_GETDATA, [O_PROT, 1])
    cpc = data[4]
    masters[device]['cpc'] = cpc
    masters[device]['extprot'] = cpc & 0x01
    masters[device]['autosend'] = (cpc >> 1) & 0x01
    masters[device]['handshake'] = (cpc >> 2) & 0x01
    masters[device]['password'] = (cpc >> 4) & 0x01
    masters[device]['punch'] = (cpc >> 7) & 0x01
    return tty
