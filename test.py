#!/usr/bin/python3

import sportident, logging

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

logging.debug("Starting SI.")

port = sportident.station_detect()

if len(port) <= 0:
    print("No master station detected.")
else:
    print("Detected master station at: {}".format(port))

    si = sportident.Si(port[0])
    print(si)

    si.setime()
