# %%
import sys
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
            "Auto cleaning interval": f"{pm_sensor.get_auto_cleaning_interval()} s"}
        print(pm_sensor_cfg)
        with open(f"{cfg['data']}/sps30.json", "at") as fh:
            fh.write(json.dumps(pm_sensor_cfg))
        pm_sensor.start_measurement()
        sleep(5)

    co2_sensor = None    
    if cfg["sensors"]["scd30"]:
        c02_sensor = SCD30()
        c02_sensor_cfg = {
            "Product type": "SCD30",
            "Firmware version": f"{c02_sensor.get_firmware_version()}"}
        print(c02_sensor_cfg)
        with open(f"{cfg['data']}/scd30.json", "at") as fh:
            fh.write(json.dumps(c02_sensor_cfg))
        c02_sensor.start_measurement()
        sleep(5)

    # main loop
    # TODO: proper scheduling instead of sleep()
    while True:
        try:
            if pm_sensor:
                with open(f"{cfg['data']}/sps30.json", "at") as fh:
                    fh.write(json.dumps(pm_sensor.get_measurement(), indent=2))
                print(json.dumps(pm_sensor.get_measurement(), indent=2))

            if co2_sensor:
                with open(f"{cfg['data']}/scd30.json", "at") as fh:
                    fh.write(json.dumps(c02_sensor.get_measurement(), indent=2))
                print(json.dumps(c02_sensor.get_measurement(), indent=2))
            sleep(2)

        except KeyboardInterrupt:
            print("Stopping measurement...")
            pm_sensor.stop_measurement()
            c02_sensor.stop_measurement()
            sys.exit()
