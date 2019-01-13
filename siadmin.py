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
        if self.rdata[5] == 0: self.rdata[5] = 1   # Repair not set date
        if self.rdata[6] == 0: self.rdata[6] = 1   # Repair not set date
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
        logging.debug("Battery consumed: {:.2f} mAh.".format(consumed/3600))
        self.handshake(si.C_GETDATA, (si.O_BATCAP, 4))
        capacity = (self.rdata[5] << 24) + (self.rdata[6] << 16) + (self.rdata[7] << 8) + self.rdata[8]
        logging.debug("Battery capacity: {:.2f} mAh.".format(capacity/3600))
        return round(100 * (1 - consumed/capacity))

    def getbatvoltage(self):
        '''Read battery voltage.'''
        self.handshake(si.C_GETDATA, (si.O_BATVOLT, 2))
        voltage = (self.rdata[5] << 8) + self.rdata[6]
        if voltage > 13100: voltage /= 131
        return voltage / 100

    def getbatemp(self):
        '''Read battery temperature.'''
        self.handshake(si.C_GETDATA, (si.O_BATTEMP, 2))
        temper = (self.rdata[5] << 8) + self.rdata[6]
        if temper >= 25800:
            return (temper - 25800) / 92
        else:
            return temper / 10

    def getbatdate(self):
        '''Read battery change date.'''
        self.handshake(si.C_GETDATA, (si.O_BATDATE, 3))
        if self.rdata[5] < 80: year = 2000 + self.rdata[5]
        else: year = 1900 + self.rdata[5]
        return datetime.date(year, self.rdata[6], self.rdata[7])

    def getbatall(self):
        '''Read all battery data at once.
           Returns: date, percent, voltage, temperature.'''
        self.handshake(si.C_GETDATA, (si.O_BATALL, 63))
        # Date
        if self.rdata[5] < 80: year = 2000 + self.rdata[5]
        else: year = 1900 + self.rdata[5]
        changedate = datetime.date(year, self.rdata[6], self.rdata[7])
        # Capacity
        capacity = (self.rdata[3+5] << 24) + (self.rdata[3+6] << 16) + (self.rdata[3+7] << 8) + self.rdata[3+8]
        logging.debug("Battery capacity: {:.2f} mAh.".format(capacity/3600))
        # Consumed
        consumed = (self.rdata[31+5] << 24) + (self.rdata[31+6] << 16) + (self.rdata[31+7] << 8) + self.rdata[31+8]
        logging.debug("Battery consumed: {:.2f} mAh.".format(consumed/3600))
        # Voltage
        voltage = (self.rdata[59+5] << 8) + self.rdata[59+6]
        if voltage > 13100: voltage /= 131
        voltage /= 100
        temper = (self.rdata[61+5] << 8) + self.rdata[61+6]
        if temper >= 25800: temper = (temper - 25800) / 92
        else: temper = temper / 10
        return changedate, round(100 * (1 - consumed/capacity)), voltage, temper

    def beep(self, times=1):
        '''Beep several times.'''
        self.handshake(si.C_BEEP, (times,))
        return times

    def getprot(self):
        '''Read communication protocol info.'''
        # Already read during init and saved in class attributes
        return {'extprot': self.extprot,
                'autosend': self.autosend,
                'handshk': self.handshk,
                'password': self.password,
                'punchread': self.punchread}

    def setprot(self, prot={}):
        '''Set communication protocol parameters.'''
        cpc = self.cpc
        if 'extprot' in prot:
            cpc = si.set_bit(cpc, 0, prot['extprot'])
        if 'autosend' in prot:
            cpc = si.set_bit(cpc, 1, prot['autosend'])
        if 'handshk' in prot:
            cpc = si.set_bit(cpc, 2, prot['handshk'])
        if 'password' in prot:
            cpc = si.set_bit(cpc, 4, prot['password'])
        if 'punchread' in prot:
            cpc = si.set_bit(cpc, 7, prot['punchread'])
        self.handshake(si.C_SETDATA, (si.O_PROT, cpc))

    def setcnmode(self, cn, mode='Control'):
        '''Set control number and mode.'''
        if not 1 <= cn <= 255:
            raise si.SiException('Control number not in range 1-255.')
        if mode not in si.MODES:
            raise si.SiException('Unknown station mode.')
        self.handshake(si.C_SETDATA, (si.O_MODE, si.MODES.index(mode), cn))

    def setbatdate(self, date):
        '''Set battery change date.'''
        self.handshake(si.C_SETDATA, (si.O_BATDATE, date.year % 100, date.month, date.day))

