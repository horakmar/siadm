#!/usr/bin/python3
#
################################################
# Package for sportident admin operations
#
# Author:  Martin Horak
# Version: 1.1
# Date:    12. 1. 2019
#
################################################

import sportident as si
import datetime, logging

class SiAdmin(si.Si):
    '''SI Administration tasks'''

    def setremote(self):
        '''Set communication to remote (controlled station).'''
        self.handshake(si.C_SETMSMODE, (si.MODE_REMOTE,))

    def setlocal(self):
        '''Set communication to local (master station itself).'''
        self.handshake(si.C_SETMSMODE, (si.MODE_LOCAL,))

    def off(self):
        '''Turn station off.'''
        self.handshake(si.C_OFF)

    def getime(self):
        '''Read station time.'''
        self.handshake(si.C_GETTIME)
        td = self.rdata[7]
        is_pm = td & 0x01
        secs = (self.rdata[8] << 8) + self.rdata[9] + is_pm * 43200;
        subsec = int(self.rdata[10] * 1000000/256)
        return datetime.datetime(2000+self.rdata[4], self.rdata[5], self.rdata[6], secs // 3600, (secs % 3600) // 60, secs % 60, subsec)

    def getmodecn(self):
        '''Read station mode and number.'''
        self.handshake(si.C_GETDATA, (si.O_MODE, 2))
        return self.rdata[5:7]

    def getfwversion(self):
        '''Read firmware version (string).'''
        self.handshake(si.C_GETDATA, (si.O_FWVER, 3))
        return bytes(self.rdata[5:8])

    def getbatstate(self):
        '''Read battery status. Returns: Remaining percent.'''
        self.handshake(si.C_GETDATA, (si.O_BATCONS, 4))
        consumed = (self.rdata[5] << 24) + (self.rdata[6] << 16) + (self.rdata[7] << 8) + self.rdata[8]
        logging.debug("Battery consumed: {}".format(consumed))
        self.handshake(si.C_GETDATA, (si.O_BATCAP, 4))
        capacity = (self.rdata[5] << 24) + (self.rdata[6] << 16) + (self.rdata[7] << 8) + self.rdata[8]
        logging.debug("Battery capacity: {}".format(capacity))
        return round(100 * (1 - consumed/capacity))

    def getbatvoltage(self):
        '''Read battery voltage.'''
        self.handshake(si.C_GETDATA, (si.O_BATVOLT, 2))
        voltage = (self.rdata[5] << 8) + self.rdata[6]
        if voltage > 13100: voltage /= 131
        return voltage / 100

