# %%
import sys
import os
import json
from time import sleep
import yaml
from sps30.sps30 import SPS30
from scd30.scd30 import SCD30

# %%
if __name__ == "__main__":

    # read config file
    with open("app.cfg", "r") as f:
        cfg = yaml.safe_load(f)
        f.close()

    pm_sensor = None
    if cfg["sensors"]["sps30"]:
        pm_sensor = SPS30()
        pm_sensor_cfg = {
            "Product type": pm_sensor.get_product_type(), 
            "Serial number": pm_sensor.get_serial_number(),
            "Firmware version": pm_sensor.get_firmware_version(),
            "Status register": pm_sensor.get_status_register(),
            "Auto cleaning interval": pm_sensor.get_auto_cleaning_interval()
            }
        print(pm_sensor_cfg)
        with open(os.path.expanduser(cfg['data']) + "/sps30.json", "wt") as fh:
            fh.write(json.dumps(pm_sensor_cfg))
        pm_sensor.start_measurement()
        sleep(5)

    co2_sensor = None    
    if cfg["sensors"]["scd30"]:
        co2_sensor = SCD30(sampling_period=60)
        co2_sensor_cfg = {
            "Product type": "SCD30",
            "Firmware version": co2_sensor.get_firmware_version()
            }
        print(co2_sensor_cfg)
        with open(os.path.expanduser(cfg['data']) + "/scd30.json", "wt") as fh:
            fh.write(json.dumps(co2_sensor_cfg))
            fh.write("\n")
        co2_sensor.start_measurement()
        sleep(5)

    # main loop
    # TODO: proper scheduling instead of sleep()
    while True:
        try:
            if pm_sensor:
                pm_result = json.dumps(pm_sensor.get_measurement(), indent=2)
                with open(os.path.expanduser(cfg['data']) + "/sps30.json", "at") as fh:
                    fh.write(pm_result)
                print(pm_result)

            if co2_sensor:
                result = co2_sensor.get_measurement()
                with open(os.path.expanduser(cfg['data']) + "/scd30.json", "at") as fh:
                    fh.write(f"{result['CO2']},{result['T']},{result['RH']}\n")
                print(json.dumps(result, indent=2))
            sleep(60)

        except KeyboardInterrupt:
            print("Stopping measurement...")
            pm_sensor.stop_measurement()
            co2_sensor.stop_measurement()
            sys.exit()
