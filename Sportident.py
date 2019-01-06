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

# Status constants
DATAOK = 0x20;
NODATA = 0x21;
BADCRC = 0x22;
BADATA = 0x23;

SI_VENDOR_ID = '10c4'
SI_PRODUCT_ID = '800a'
SI_CHUNK = 256

# Commands
C_SETMSMODE = 0xf0; # mode
C_SETTIME   = 0xf6; # p1..p7
C_GETTIME   = 0xf7;
C_OFF       = 0xf8;
C_BEEP      = 0xf9; # numbeeps
C_SETSPEED  = 0xfe; # speed
C_GETMEM    = 0x81; # adr2, adr1, adr0, numbytes
C_CLEARMEM  = 0xf5;
C_SETDATA   = 0x82; # offset, [data]
C_GETDATA   = 0x83; # offset, numbytes
C_GETSI5    = 0xb1;
C_GETSI6    = 0xe1; # bn
C_GETSI8    = 0xef; # bn

# Autosend commands
C_INSI5     = 0xe5; # cn1, cn0, si3..si0
C_INSI6     = 0xe6; # cn1, cn0, si3..si0
C_INSI8     = 0xe8; # cn1, cn0, si3..si0
C_OUTSI     = 0xe7; # cn1, cn0, si3..si0
C_PUNCH     = 0xd3; # cn1, cn0, si3..si0, td, th, tl, tss, mem2..mem0

# Arguments
MODE_LOCAL = 0x4d;
MODE_REMOTE = 0x53;
SPEED_38400 = 0x01;
SPEED_4800  = 0x00;

# Offsets           # Len
O_MODE      = 0x71; # 1
O_CODE      = 0x72; # 2
O_PROT      = 0x74; # 1

import os, logging, serial, time

##################################
# Custom exceptions
##################################
class SiException(Exception):
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
    return crc_l(length, data)

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
def frame(command, data):
    """Add framing to output data."""
    length = len(data)
    data[:0] = (command, length)
    crcsum = crc(data);
    data[:0] = (WAKE, STX)
    data.extend((crcsum >> 8, crcsum & 0xff, ETX))
    return data

#--------------------------------#
def unframe(data):
    """Strip framing from input data."""
    d = data.pop(0)
    while len(data) > 0:
        if d == STX: break
        elif d == NAK: return NAK, ()
        elif d == ACK: return ACK, ()
        d = data.pop(0)
    else:
        return NODATA, ()
    return DATAOK, data

def checkcrc(data):
    """Check CRC of received data."""
    length = data[1]
    data_crc = (data[length+2] << 8) + data[length+3]
    comp_crc = crc_l(length+2, data)
    if data_crc == comp_crc:
        return True
    else:
        logging.warning("Bad CRC. Received: {}, Computed: {}".format(data_crc, comp_crc))
        return False

#--------------------------------#
def siread(tty):
    """Read data from SI station."""
    rdata = tty.read(SI_CHUNK)
    if rdata:
        logging.debug("<i<<< " + ':'.join('{:02x}'.format(x) for x in rdata))
        (status, data) = unframe(list(rdata))
    else:
        return NODATA, ()
    if status == DATAOK:
        if not checkcrc(data):
            status = BADCRC
    return(status, data)

#--------------------------------#
def siwrite(tty, command, data=[]):
    """Write data to SI station."""
    fdata = frame(command, data)
    tty.write(bytearray(fdata))
    logging.debug(">o>>> " + ':'.join('{:02x}'.format(x) for x in fdata))
    return

#--------------------------------#
def handshake(tty, tries, command, wdata):
    """Try write - read cycle tries times."""
    while tries > 0:
        siwrite(tty, command, wdata)
        (status, rdata) = siread(tty)
        if status == DATAOK:
            return rdata
        else:
            tries -= 1
            logging.warning("Bad status, {} tries left.".format(tries))
            time.sleep(1)
    raise SiException("Handshake failed")

def sinit(device, ms_opt):
    """Initialize serial communication with SI master station."""
    bauds = (38400, 4800)
    for baudrate in bauds:
        try:
            tty = serial.Serial('/dev/'+device, baudrate, rtscts=True, timeout=0.2)   # Timeout 0.2 sec is reliable
            data = handshake(tty, 1, C_SETMSMODE, [MODE_LOCAL])
        except SiException: tty.close()
        else: break
    else:
        raise SiException("Cannot set baudrate.")

    ms_opt['cn'] = (data[2] << 8) + data[3]
    data = handshake(tty, 3, C_GETDATA, [O_PROT, 1])     # Get protocol information
    ms_opt['cpc'] = data[5]
    ms_opt['extprot'] = data[5] & 0x01
    ms_opt['autosend'] = (data[5] >> 1) & 0x01
    ms_opt['handshake'] = (data[5] >> 2) & 0x01
    ms_opt['password'] = (data[5] >> 4) & 0x01
    ms_opt['punch'] = (data[5] >> 7) & 0x01
    ms_opt['speed'] = baudrate
    return tty

def setime(tty, tries):
    '''
    Set station time to computer time.
    Try to count difference with multiple tries.
    '''
    while tries > 0:
        ctime = time.localtime()
        if ctime.tm_hour >= 12:
            is_pm = 1
            hour = ctime.tm_hour - 12
        else:
            is_pm = 0

        handshake(tty, 1, C_SETTIME, ctime.tm_year % 100, ctime.tm_mon, ctime.tm_mday
