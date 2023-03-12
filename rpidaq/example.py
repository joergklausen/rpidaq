"""
Credits: https://github.com/dvsu/sps30

MIT License

Copyright (c) 2021 Dave

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import sys
import json
from time import sleep
from sps30.sps30 import SPS30


if __name__ == "__main__":
    pm_sensor = SPS30()
    print(f"Firmware version: {pm_sensor.firmware_version()}")
    print(f"Product type: {pm_sensor.product_type()}")
    print(f"Serial number: {pm_sensor.serial_number()}")
    print(f"Status register: {pm_sensor.read_status_register()}")
    print(
        f"Auto cleaning interval: {pm_sensor.read_auto_cleaning_interval()} s")
#    print(f"Set auto cleaning interval: {pm_sensor.write_auto_cleaning_interval_days(2)} s")
    pm_sensor.start_measurement()
    sleep(5)
    
    while True:
        try:
            print(json.dumps(pm_sensor.get_measurement(), indent=2))
            sleep(2)

        except KeyboardInterrupt:
            print("Stopping measurement...")
            pm_sensor.stop_measurement()
            sys.exit()