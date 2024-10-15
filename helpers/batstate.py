#!/usr/bin/python3

# Read battery state of all stations, write into file

import siadmin as sa
import sportident as si

filename = 'si_batstat.csv'
r = ''

with open(filename, 'a') as wfile:
    ports = si.station_detect()
    siadm = sa.SiAdmin(ports[0])
    siadm.setremote()
    wfile.write("\n\n#Code;Mode;Voltage;Date\n")
    while True:
        r = input("Enter q to quit: ")
        if r.lower() == 'q': break
        try:
            mode,code = siadm.getmodecn()
            bvolt = siadm.getbatvoltage()
            bdate = siadm.getbatdate()
            print("{};{};{:4.2f};{}".format(code, si.MODES[mode], bvolt, bdate))
            wfile.write("{};{};{:4.2f};{}\n".format(code, si.MODES[mode], bvolt, bdate))
        except si.SiException:
            print("Station do not communicate.")

wfile.close()
