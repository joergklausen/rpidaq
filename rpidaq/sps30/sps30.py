#!/usr/bin/env python

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
import threading
import logging
from time import sleep
from queue import Queue
from datetime import datetime
from common.i2c import I2C
from common.crc import CRC

# I2C commands
CMD_START_MEASUREMENT = [0x00, 0x10]
CMD_STOP_MEASUREMENT = [0x01, 0x04]
CMD_GET_DATA_READY_FLAG = [0x02, 0x02]
CMD_GET_MEASURED_VALUES = [0x03, 0x00]
CMD_SLEEP = [0x10, 0x01]
CMD_WAKEUP = [0x11, 0x03]
CMD_START_FAN_CLEANING = [0x56, 0x07]
CMD_GET_AUTO_CLEANING_INTERVAL = [0x80, 0x04]
CMD_GET_PRODUCT_TYPE = [0xD0, 0x02]
CMD_GET_SERIAL_NUMBER = [0xD0, 0x33]
CMD_GET_FIRMWARE_VERSION = [0xD1, 0x00]
CMD_GET_STATUS_REGISTER = [0xD2, 0x06]
CMD_CLEAR_STATUS_REGISTER = [0xD2, 0x10]
CMD_RESET = [0xD3, 0x04]

# Length of response in bytes
NBYTES_GET_DATA_READY_FLAG = 3
NBYTES_MEASURED_VALUES_FLOAT = 60  # IEEE754 float
NBYTES_MEASURED_VALUES_INTEGER = 30  # unsigned 16 bit integer
NBYTES_GET_AUTO_CLEANING_INTERVAL = 6
NBYTES_GET_PRODUCT_TYPE = 12
NBYTES_GET_SERIAL_NUMBER = 48
NBYTES_GET_FIRMWARE_VERSION = 3
NBYTES_GET_STATUS_REGISTER = 6

# Packet size including checksum byte [data1, data2, checksum]
PACKET_SIZE = 3

# Size of each measurement data packet (PMx) including checksum bytes, in bytes
SIZE_FLOAT = 6  # IEEE754 float
SIZE_INTEGER = 3  # unsigned 16 bit integer

class SPS30:

    def __init__(self,  bus:int = 1, address:int = 0x69, sampling_period:int = 1, logger:str = None):
        self.logger = None
        if logger:
            self.logger = logging.getLogger(logger)

        self.sampling_period = sampling_period
        self.i2c = I2C(bus, address)
        self.crc = CRC()
        self.__data = Queue(maxsize=20)
        self.__valid = {
            "mass_density": False,
            "particle_count": False,
            "particle_size": False
        }


    def get_firmware_version(self) -> str:
        self.i2c.write(CMD_GET_FIRMWARE_VERSION)
        data = self.i2c.read(NBYTES_GET_FIRMWARE_VERSION)

        if self.crc.calc(data[:2]) != data[2]:
            return "CRC mismatched"

        return ".".join(map(str, data[:2]))

    def get_product_type(self) -> str:
        self.i2c.write(CMD_GET_PRODUCT_TYPE)
        data = self.i2c.read(NBYTES_GET_PRODUCT_TYPE)
        result = ""

        for i in range(0, NBYTES_GET_PRODUCT_TYPE, 3):
            if self.crc.calc(data[i:i+2]) != data[i+2]:
                return "CRC mismatched"

            result += "".join(map(chr, data[i:i+2]))
        if result == "00080000":
            result = "SPS30"
            
        return result

    def get_serial_number(self) -> str:
        self.i2c.write(CMD_GET_SERIAL_NUMBER)
        data = self.i2c.read(NBYTES_GET_SERIAL_NUMBER)
        result = ""

        for i in range(0, NBYTES_GET_SERIAL_NUMBER, PACKET_SIZE):
            if self.crc.calc(data[i:i+2]) != data[i+2]:
                return "CRC mismatched"

            result += "".join(map(chr, data[i:i+2]))

        return result

    def get_status_register(self) -> dict:
        self.i2c.write(CMD_GET_STATUS_REGISTER)
        data = self.i2c.read(NBYTES_GET_STATUS_REGISTER)

        status = []
        for i in range(0, NBYTES_GET_STATUS_REGISTER, PACKET_SIZE):
            if self.crc.calc(data[i:i+2]) != data[i+2]:
                return "CRC mismatched"

            status.extend(data[i:i+2])

        binary = '{:032b}'.format(
            status[0] << 24 | status[1] << 16 | status[2] << 8 | status[3])
        speed_status = "too high/ too low" if int(binary[10]) == 1 else "ok"
        laser_status = "out of range" if int(binary[26]) == 1 else "ok"
        fan_status = "0 rpm" if int(binary[27]) == 1 else "ok"

        return {
            "speed_status": speed_status,
            "laser_status": laser_status,
            "fan_status": fan_status
        }


    def clear_status_register(self) -> None:
        self.i2c.write(CMD_CLEAR_STATUS_REGISTER)


    def get_data_ready_flag(self) -> bool:
        self.i2c.write(CMD_GET_DATA_READY_FLAG)
        data = self.i2c.read(NBYTES_GET_DATA_READY_FLAG)

        if self.crc.calc(data[:2]) != data[2]:
            if self.logger:
                self.logger.warning(
                    "'get_data_ready_flag' CRC mismatched!" +
                    f"  Data: {data[:2]}" +
                    f"  Calculated CRC: {self.crc.calc(data[:2])}" +
                    f"  Expected: {data[2]}")
            else:
                print(
                    "'get_data_ready_flag' CRC mismatched!" +
                    f"  Data: {data[:2]}" +
                    f"  Calculated CRC: {self.crc.calc(data[:2])}" +
                    f"  Expected: {data[2]}")

            return False

        return True if data[1] == 1 else False


    def sleep(self) -> None:
        self.i2c.write(CMD_SLEEP)


    def wakeup(self) -> None:
        self.i2c.write(CMD_WAKEUP)


    def start_fan_cleaning(self) -> None:
        self.i2c.write(CMD_START_FAN_CLEANING)


    def get_auto_cleaning_interval(self) -> int:
        self.i2c.write(CMD_GET_AUTO_CLEANING_INTERVAL)
        data = self.i2c.read(NBYTES_GET_AUTO_CLEANING_INTERVAL)

        interval = []
        for i in range(0, NBYTES_GET_AUTO_CLEANING_INTERVAL, 3):
            if self.crc.calc(data[i:i+2]) != data[i+2]:
                return "CRC mismatched"

            interval.extend(data[i:i+2])

        return (interval[0] << 24 | interval[1] << 16 | interval[2] << 8 | interval[3])


    def set_auto_cleaning_interval(self, days: int) -> int:
        seconds = days * 86400  # 1day = 86400sec
        interval = []
        interval.append((seconds & 0xff000000) >> 24)
        interval.append((seconds & 0x00ff0000) >> 16)
        interval.append((seconds & 0x0000ff00) >> 8)
        interval.append(seconds & 0x000000ff)
        data = CMD_GET_AUTO_CLEANING_INTERVAL
        data.extend([interval[0], interval[1]])
        data.append(self.crc.calc(data[2:4]))
        data.extend([interval[2], interval[3]])
        data.append(self.crc.calc(data[5:7]))
        self.i2c.write(data)
        sleep(0.05)
        return self.get_auto_cleaning_interval()


    def reset(self) -> None:
        self.i2c.write(CMD_RESET)


    def start_measurement(self) -> None:
        data_format = {
            "IEEE754_float": 0x03,
            "unsigned_16_bit_integer": 0x05
        }

        data = CMD_START_MEASUREMENT
        data.extend([data_format["IEEE754_float"], 0x00])
        data.append(self.crc.calc(data[2:4]))
        self.i2c.write(data)
        sleep(0.05)
        self.__run()


    def get_measurement(self) -> dict:
        if self.__data.empty():
            return {}

        return self.__data.get()


    def stop_measurement(self) -> None:
        self.i2c.write(CMD_STOP_MEASUREMENT)
        self.i2c.close()


    def __ieee754_number_conversion(self, data: int) -> float:
        binary = "{:032b}".format(data)

        sign = int(binary[0:1])
        exp = int(binary[1:9], 2) - 127

        divider = 0
        if exp < 0:
            divider = abs(exp)
            exp = 0

        mantissa = binary[9:]

        real = int(('1' + mantissa[:exp]), 2)
        decimal = mantissa[exp:]

        dec = 0.0
        for i in range(len(decimal)):
            dec += int(decimal[i]) / (2**(i+1))

        if divider == 0:
            return round((((-1)**(sign) * real) + dec), 3)
        else:
            return round((((-1)**(sign) * real) + dec) / pow(2, divider), 3)


    def __mass_density_measurement(self, data: list) -> dict:
        category = ["pm1.0", "pm2.5", "pm4.0", "pm10"]

        density = {
            "pm1.0": 0.0,
            "pm2.5": 0.0,
            "pm4.0": 0.0,
            "pm10": 0.0
        }

        for block, (pm) in enumerate(category):
            pm_data = []
            for i in range(0, SIZE_FLOAT, PACKET_SIZE):
                offset = (block * SIZE_FLOAT) + i
                if self.crc.calc(data[offset:offset+2]) != data[offset+2]:
                    if self.logger:
                        self.logger.warning(
                            "'__mass_density_measurement' CRC mismatched!" +
                            f"  Data: {data[offset:offset+2]}" +
                            f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
                            f"  Expected: {data[offset+2]}")
                    else:
                        print(
                            "'__mass_density_measurement' CRC mismatched!" +
                            f"  Data: {data[offset:offset+2]}" +
                            f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
                            f"  Expected: {data[offset+2]}")
                    self.__valid["mass_density"] = False
                    return {}

                pm_data.extend(data[offset:offset+2])

            density[pm] = self.__ieee754_number_conversion(
                pm_data[0] << 24 | pm_data[1] << 16 | pm_data[2] << 8 | pm_data[3])

        self.__valid["mass_density"] = True

        return density


    def __particle_count_measurement(self, data: list) -> dict:
        category = ["pm0.5", "pm1.0", "pm2.5", "pm4.0", "pm10"]

        count = {
            "pm0.5": 0.0,
            "pm1.0": 0.0,
            "pm2.5": 0.0,
            "pm4.0": 0.0,
            "pm10": 0.0
        }

        for block, (pm) in enumerate(category):
            pm_data = []
            for i in range(0, SIZE_FLOAT, PACKET_SIZE):
                offset = (block * SIZE_FLOAT) + i
                if self.crc.calc(data[offset:offset+2]) != data[offset+2]:
                    if self.logger:
                        self.logger.warning(
                            "'__particle_count_measurement' CRC mismatched!" +
                            f"  Data: {data[offset:offset+2]}" +
                            f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
                            f"  Expected: {data[offset+2]}")
                    else:
                        print(
                            "'__particle_count_measurement' CRC mismatched!" +
                            f"  Data: {data[offset:offset+2]}" +
                            f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
                            f"  Expected: {data[offset+2]}")

                    self.__valid["particle_count"] = False
                    return {}

                pm_data.extend(data[offset:offset+2])

            count[pm] = self.__ieee754_number_conversion(
                pm_data[0] << 24 | pm_data[1] << 16 | pm_data[2] << 8 | pm_data[3])

        self.__valid["particle_count"] = True

        return count


    def __particle_size_measurement(self, data: list) -> float:
        size = []
        for i in range(0, SIZE_FLOAT, PACKET_SIZE):
            if self.crc.calc(data[i:i+2]) != data[i+2]:
                if self.logger:
                    self.logger.warning(
                        "'__particle_size_measurement' CRC mismatched!" +
                        f"  Data: {data[i:i+2]}" +
                        f"  Calculated CRC: {self.crc.calc(data[i:i+2])}" +
                        f"  Expected: {data[i+2]}")
                else:
                    print(
                        "'__particle_size_measurement' CRC mismatched!" +
                        f"  Data: {data[i:i+2]}" +
                        f"  Calculated CRC: {self.crc.calc(data[i:i+2])}" +
                        f"  Expected: {data[i+2]}")

                self.__valid["particle_size"] = False
                return 0.0

            size.extend(data[i:i+2])

        self.__valid["particle_size"] = True

        return self.__ieee754_number_conversion(size[0] << 24 | size[1] << 16 | size[2] << 8 | size[3])


    def __get_measured_value(self) -> None:
        while True:
            try:
                if not self.get_data_ready_flag():
                    continue

                self.i2c.write(CMD_GET_MEASURED_VALUES)
                data = self.i2c.read(NBYTES_MEASURED_VALUES_FLOAT)

                if self.__data.full():
                    self.__data.get()

                result = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "mass_density": self.__mass_density_measurement(data[:24]),
                    "particle_count": self.__particle_count_measurement(data[24:54]),
                    "particle_size": self.__particle_size_measurement(data[54:]),
                    "mass_density_unit": "μg/m3",
                    "particle_count_unit": "#/cm3",
                    "particle_size_unit": "μm"
                }

                self.__data.put(result if all(self.__valid.values()) else {})

            except KeyboardInterrupt:
                if self.logger:
                    self.logger.warning("Stopping measurement...")
                else:
                    print("Stopping measurement...")

                self.stop_measurement()
                sys.exit()

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"{type(e).__name__}: {e}")
                else:
                    print(f"{type(e).__name__}: {e}")

            finally:
                sleep(self.sampling_period)


    def __run(self) -> None:
        threading.Thread(target=self.__get_measured_value,
                         daemon=True).start()


if __name__ == "__main__":
    pass
