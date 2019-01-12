#!/usr/bin/python3

import sportident, siadmin, logging

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

logging.debug("Starting SI.")

port = sportident.station_detect()

if len(port) <= 0:
    print("No master station detected.")
else:
    print("Detected master station at: {}".format(port))

    si = siadmin.SiAdmin(port[0])
    print(si)
    si.setlocal()
    time = si.getime()
    print("time: ",time)

    mode,cn = si.getmodecn()
    print("Mode: {}, Number: {}".format(sportident.MODES[mode], cn))
    print("Firmware: {}".format(si.getfwversion().decode()))
    print("Battery: state: {}, voltage: {}".format(si.getbatstate(), si.getbatvoltage()))
