# SPORTident Admin

This is simple CLI software for administering of SPORTident (SI) stations.  
Written in Python, old obsolete version in Perl.

## Features
### SI stations reading and writing: 
  * Mode
  * Code
  * Time
  * Protocol info
  * Battery change date

### Only reading:
  * Battery status
  * Firmware version

### Only Writing (commands):
  * Beep
  * Turn off

### TODO (maybe):
  * Read backup memory
  * Update firmware


## Dependencies

Pyserial: https://pypi.org/project/pyserial/


## How to connect to WSL
https://learn.microsoft.com/en-us/windows/wsl/connect-usb

  1. Install usbipd-win from https://github.com/dorssel/usbipd-win/releases

  2. Connect readout station to comp and find it's USB-ID (PowerShell)
  ```posh
  usbipd list
  ```
  3. Share the device (PowerShell)
  ```posh
  usbipd bind --busid <busid>
  ```

  4. Attach USB device (PowerShell)
  ```posh
  usbipd attach --wsl --busid <busid>
  ```

  5. Detach the device when done (PowerShell)
  ```posh
  usbipd detach --busid <busid>
  ```