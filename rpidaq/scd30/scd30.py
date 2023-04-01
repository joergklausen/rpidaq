#!/usr/bin/env python

"""
Credits: This driver is heavily inspired by the great work done by Dave for the Sensition SPS30 particle sensor (https://github.com/dvsu)

MIT License

Copyright (c) 2023 Jörg Klausen

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
# CMD_SLEEP = [0x10, 0x01]
# CMD_WAKEUP = [0x11, 0x03]
# CMD_START_FAN_CLEANING = [0x56, 0x07]
# CMD_GET_AUTO_CLEANING_INTERVAL = [0x80, 0x04]
CMD_SET_ALTITUDE = [0x51, 0x02]
# CMD_GET_PRODUCT_TYPE = [0xD0, 0x02]
# CMD_GET_SERIAL_NUMBER = [0xD0, 0x33]
CMD_GET_FIRMWARE_VERSION = [0xD1, 0x00]
# CMD_GET_STATUS_REGISTER = [0xD2, 0x06]
# CMD_CLEAR_STATUS_REGISTER = [0xD2, 0x10]
CMD_RESET = [0xD3, 0x04]

# Length of response in bytes
NBYTES_GET_DATA_READY_FLAG = 3
NBYTES_MEASURED_VALUES_FLOAT = 18  # IEEE754 float
# NBYTES_MEASURED_VALUES_INTEGER = 30  # unsigned 16 bit integer
# NBYTES_GET_AUTO_CLEANING_INTERVAL = 6
# NBYTES_GET_PRODUCT_TYPE = 12
# NBYTES_GET_SERIAL_NUMBER = 48
NBYTES_GET_FIRMWARE_VERSION = 3
NBYTES_GET_STATUS_REGISTER = 6

# Packet size including checksum byte [data1, data2, checksum]
PACKET_SIZE = 3

# Size of each measurement data packet (PMx) including checksum bytes, in bytes
SIZE_FLOAT = 6  # IEEE754 float
SIZE_INTEGER = 3  # unsigned 16 bit integer

class SCD30:

    def __init__(self,  bus: int = 1, address: int = 0x61, sampling_period: int = 1, logger: str = None):
        self.logger = None
        if logger:
            self.logger = logging.getLogger(logger)

        self.sampling_period = sampling_period
        self.i2c = I2C(bus, address)
        self.crc = CRC()
        self.__data = Queue(maxsize=20)
        self.__valid = {
            "CO2": False,
            "T": False,
            "RH": False
        }

    def get_firmware_version(self) -> str:
        self.i2c.write(CMD_GET_FIRMWARE_VERSION)
        data = self.i2c.read(NBYTES_GET_FIRMWARE_VERSION)

        if self.crc.calc(data[:2]) != data[2]:
            return "CRC mismatched"

        return ".".join(map(str, data[:2]))

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

    def reset(self) -> None:
        self.i2c.write(CMD_RESET)

    def start_measurement(self) -> None:
        data_format = {
            "IEEE754_float": 0x03,
            "unsigned_16_bit_integer": 0x05
        }

        data = CMD_START_MEASUREMENT
        pressure = 0 #960
        data.extend(pressure.to_bytes(2, 'big'))
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

#     def __CO2_measurement(self, data: list) -> int:
# #         category = ["MMSB", "MLSB", "LMSB", "LLSB"]
# # 
# #         co2_conc = {
# #             "MMSB": 0.0,
# #             "MLSB": 0.0,
# #             "LMSB": 0.0,
# #             "LLSB": 0.0
# #         }
#         category = ["CO2"]

#         co2_conc = {
#             "CO2": 0.0
#         }

#         for block, (co2) in enumerate(category):
#             co2_data = []
#             for i in range(0, SIZE_FLOAT, PACKET_SIZE):
#                 offset = (block * SIZE_FLOAT) + i
#                 if self.crc.calc(data[offset:offset+2]) != data[offset+2]:
#                     if self.logger:
#                         self.logger.warning(
#                             "'__CO2_measurement' CRC mismatched!" +
#                             f"  Data: {data[offset:offset+2]}" +
#                             f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
#                             f"  Expected: {data[offset+2]}")
#                     else:
#                         print(
#                             "'__CO2_measurement' CRC mismatched!" +
#                             f"  Data: {data[offset:offset+2]}" +
#                             f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
#                             f"  Expected: {data[offset+2]}")
#                     self.__valid["CO2"] = False
#                     return {}

#                 co2_data.extend(data[offset:offset+2])

#             co2_conc[co2] = self.__ieee754_number_conversion(
#                 co2_data[0] << 24 | co2_data[1] << 16 | co2_data[2] << 8 | co2_data[3])

#         self.__valid["CO2"] = True

#         return co2_conc

    def __measurement(self, data: list) -> int:
        category = ["CO2", "T", "RH"]

        reading = {
            "CO2": 0.0,
            "T": 0.0,
            "RH": 0.0
        }

        for block, (x) in enumerate(category):
            measured_data = []
            for i in range(0, SIZE_FLOAT, PACKET_SIZE):
                offset = (block * SIZE_FLOAT) + i
                if self.crc.calc(data[offset:offset+2]) != data[offset+2]:
                    if self.logger:
                        self.logger.warning(
                            "'__measurement' CRC mismatched!" +
                            f"  Data: {data[offset:offset+2]}" +
                            f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
                            f"  Expected: {data[offset+2]}")
                    else:
                        print(
                            "'__measurement' CRC mismatched!" +
                            f"  Data: {data[offset:offset+2]}" +
                            f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
                            f"  Expected: {data[offset+2]}")
                    self.__valid["CO2"] = False
                    return {}

                measured_data.extend(data[offset:offset+2])

            reading[x] = self.__ieee754_number_conversion(
                measured_data[0] << 24 | measured_data[1] << 16 | measured_data[2] << 8 | measured_data[3])

        # self.__valid["CO2"] = True
        self.__valid = {
            "CO2": True,
            "T": True,
            "RH": True
        }

        return reading

    # def __T_measurement(self, data: list) -> dict:
    #     category = ["T"]

    #     temp_value = {
    #         "T": 0.0
    #     }

    #     for block, (temp) in enumerate(category):
    #         t_data = []
    #         for i in range(0, SIZE_FLOAT, PACKET_SIZE):
    #             offset = (block * SIZE_FLOAT) + i
    #             if self.crc.calc(data[offset:offset+2]) != data[offset+2]:
    #                 if self.logger:
    #                     self.logger.warning(
    #                         "'__T_measurement' CRC mismatched!" +
    #                         f"  Data: {data[offset:offset+2]}" +
    #                         f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
    #                         f"  Expected: {data[offset+2]}")
    #                 else:
    #                     print(
    #                         "'__T_measurement' CRC mismatched!" +
    #                         f"  Data: {data[offset:offset+2]}" +
    #                         f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
    #                         f"  Expected: {data[offset+2]}")

    #                 self.__valid["T"] = False
    #                 return {}

    #             t_data.extend(data[offset:offset+2])

    #         temp_value[temp] = self.__ieee754_number_conversion(
    #             t_data[0] << 24 | t_data[1] << 16 | t_data[2] << 8 | t_data[3])

    #     self.__valid["T"] = True

    #     return temp_value

    # def __RH_measurement(self, data: list) -> dict:
    #     category = ["RH"]

    #     rh_value = {
    #         "RH": 0.0
    #     }

    #     for block, (rh) in enumerate(category):
    #         rh_data = []
    #         for i in range(0, SIZE_FLOAT, PACKET_SIZE):
    #             offset = (block * SIZE_FLOAT) + i
    #             if self.crc.calc(data[offset:offset+2]) != data[offset+2]:
    #                 if self.logger:
    #                     self.logger.warning(
    #                         "'__RH_measurement' CRC mismatched!" +
    #                         f"  Data: {data[offset:offset+2]}" +
    #                         f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
    #                         f"  Expected: {data[offset+2]}")
    #                 else:
    #                     print(
    #                         "'__RH_measurement' CRC mismatched!" +
    #                         f"  Data: {data[offset:offset+2]}" +
    #                         f"  Calculated CRC: {self.crc.calc(data[offset:offset+2])}" +
    #                         f"  Expected: {data[offset+2]}")

    #                 self.__valid["RH"] = False
    #                 return {}

    #             rh_data.extend(data[offset:offset+2])

    #         rh_value[rh] = self.__ieee754_number_conversion(
    #             rh_data[0] << 24 | rh_data[1] << 16 | rh_data[2] << 8 | rh_data[3])

    #     self.__valid["RH"] = True

    #     return rh_value

    def __get_measured_value(self) -> None:
        while True:
            try:
                if not self.get_data_ready_flag():
                    continue

                self.i2c.write(CMD_GET_MEASURED_VALUES)
                data = self.i2c.read(NBYTES_MEASURED_VALUES_FLOAT)
                print(data)
                
                if self.__data.full():
                    self.__data.get()

                result = self.__measurement(data)
                print(result)

                self.__data.put(result if all(self.__valid.values()) else {})

            except KeyboardInterrupt:
                if self.logger:
                    self.logger.warning("Stopping measurement...")
                else:
                    print("Stopping measurement...")

                self.stop_measurement()
                sys.exit()

            except Exception as err:
                if self.logger:
                    self.logger.warning(f"{type(err).__name__}: {err}")
                else:
                    print(f"{type(err).__name__}: {err}")

            finally:
                sleep(self.sampling_period)

    def __run(self) -> None:
        threading.Thread(target=self.__get_measured_value,
                         daemon=True).start()
