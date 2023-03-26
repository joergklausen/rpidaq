import sys
import json
from time import sleep
import yaml
from sps30.sps30 import SPS30


if __name__ == "__main__":

    # read config file
    with open("app.cfg", "r") as f:
        config = yaml.safe_load(f)
        f.close()

    if config["sensors"]["sps30"]:
        pm_sensor = SPS30()
        print(f"Firmware version: {pm_sensor.get_firmware_version()}")
        print(f"Product type: {pm_sensor.get_product_type()}")
        print(f"Serial number: {pm_sensor.get_serial_number()}")
        print(f"Status register: {pm_sensor.get_status_register()}")
        print(
            f"Auto cleaning interval: {pm_sensor.get_auto_cleaning_interval()} s")
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