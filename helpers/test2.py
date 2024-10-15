#!/usr/bin/python3

import sportident, siadmin, logging, datetime

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
    
    si.setime()

    time = si.getime()
    print("time: ",time)

    print("Firmware: {}".format(si.getfwversion().decode()))
    print("Battery: state: {}, voltage: {}".format(si.getbatstate(), si.getbatvoltage()))
    print("Battery: temperature: {}, change date: {}".format(si.getbatemp(), si.getbatdate()))

    si.setbatdate(datetime.date(2014,1,16))

    batdate, percent, voltage, temperature = si.getbatall()
    print("  Date: {}".format(batdate))
    print("  Status: {}".format(percent))
    print("  Voltage: {}".format(voltage))
    print("  Temperature: {}".format(temperature))

    prot = si.getprot()
    print("Protocol: {}".format(prot))

    prot['extprot'] = True
    si.setprot(prot)
    si.refreshprot()
    print("Changed protocol: {}".format(si.getprot()))

    si.setcnmode(4, 'Readout')
#    si.setcnmode(22, 'Check')
    

    mode,cn = si.getmodecn()
    print("Mode: {}, Number: {}".format(sportident.MODES[mode], cn))

    beeps = 2
    print("Beep {} times.".format(si.beep(beeps)))
    
    
