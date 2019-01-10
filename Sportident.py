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

import os, logging, serial, time

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


##################################
# Custom exceptions
##################################
class SiException(Exception):
    pass

##################################
# SI auxiliary functions
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


##################################
# SI main class
##################################
class Si():
    '''SI master station class'''
    def __init__(self, tty):
        '''Initialize serial communication with SI master station.'''
        self.tty = tty
        bauds = (38400, 4800)
        for baudrate in bauds:
            try:
                self.dev = serial.Serial('/dev/'+tty, baudrate, timeout=0.2)   # Timeout 0.2 sec is reliable
                result = self.handshake(1, C_SETMSMODE, [MODE_LOCAL])
            except SiException: self.dev.close()
            else: break
        else:
            raise SiException("Cannot set baudrate.")

        self.cn = (data[2] << 8) + data[3]
        self.speed = baudrate
        result = self.handshake(3, C_GETDATA, [O_PROT, 1])     # Get protocol information
        self.cpc = self.rdata[5]
        self.extprot = self.cpc & 0x01
        self.autosend = (self.cpc >> 1) & 0x01
        self.handshake = (self.cpc >> 2) & 0x01
        self.password = (self.cpc >> 4) & 0x01
        self.punch = (self.cpc >> 7) & 0x01

    def frame(self, command, data):
        '''Add framing to output data.'''
        length = len(data)
        self.wdata = bytearray((command, length))
        self.wdata.extend(data)
        crcsum = crc(data);
        self.wdata.insert(0, STX)
        self.wdata.insert(0,WAKE)
        self.wdata.extend((crcsum >> 8, crcsum & 0xff, ETX))
        return

    def unframe(self):
        '''Strip framing from input data.'''
        while len(self.rdata) > 0:
            d = self.rdata.pop(0)
            if d == STX: break
            elif d == NAK:
                self.status = NAK
                raise SiException("NAK returned.")
            elif d == ACK:
                self.status = ACK
                raise SiException("ACK returned.")
            d = self.rdata.pop(0)
        else:
            self.status = NODATA
            raise SiException("No readable data.")

        if self.checkcrc():
            self.status = DATAOK
            return
        else:
            self.status = BADCRC
            raise SiException("Bad CRC.")

    def checkcrc(self):
        '''Check CRC of received data.'''
        length = self.rdata[1]
        data_crc = (self.rdata[length+2] << 8) + self.rdata[length+3]
        comp_crc = crc_l(length+2, self.rdata)
        if data_crc == comp_crc:
            return True
        else:
            logging.warning("Bad CRC. Received: {}, Computed: {}".format(data_crc, comp_crc))
            return False

#--------------------------------#
    def siread(self):
        """Read data from SI station."""
        self.rdata = self.dev.read(SI_CHUNK)
        if self.rdata:
            logging.debug("<i<<< " + ':'.join('{:02x}'.format(x) for x in self.rdata))
        self.unframe()

#--------------------------------#
    def siwrite(self, command, data=[]):
        """Write data to SI station."""
        self.frame(command, data)
        self.dev.write(self.wdata)
        logging.debug(">o>>> " + ':'.join('{:02x}'.format(x) for x in self.wdata))
        return

#--------------------------------#
    def handshake(self, tries, command, data):
        """Try write - read cycle tries times."""
        while True:
            try:
                self.siwrite(command, data)
                self.siread(tty)
            except SiException:
                tries -= 1
                logging.warning("Bad status, {} tries left.".format(tries))
                if tries <= 0:
                    raise SiException("Handshake failed.")
                    break
                else:
                    time.sleep(1)


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
