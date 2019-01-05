#!/usr/bin/python3

import Sportident, logging

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

logging.debug("Starting SI.")

port = Sportident.station_detect()

print("Detected tty: {}".format(port))

si_master = {}

Sportident.sinit(port[0], si_master)

print(si_master)
