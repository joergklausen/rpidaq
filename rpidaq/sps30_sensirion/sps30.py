from struct import pack
from sensirion_i2c_driver import LinuxI2cTransceiver, I2cConnection, \
    I2cDevice, SensirionI2cCommand, CrcCalculator


# Implement a command
class MyI2cCmdReadSerialNumber(SensirionI2cCommand):
    def __init__(self):
        super(MyI2cCmdReadSerialNumber, self).__init__(
            command=0xD033,
            tx_data=[],
            rx_length=48,
            read_delay=0,
            timeout=0,
            crc=CrcCalculator(8, 0x31, 0xFF),
        )

    def interpret_response(self, data):
        raw_response = SensirionI2cCommand.interpret_response(self, data)
        return str(raw_response.decode('utf-8').rstrip('\0'))


class MyI2cCmdStartMeasurement(SensirionI2cCommand):
    def __init__(self):
        super(MyI2cCmdStartMeasurement, self).__init__(
            command=0x0010,
            tx_data=[0x03, 0x00], # 0x03 Big Endian
            rx_length=0,
            read_delay=0,
            timeout=0,
            crc=CrcCalculator(8, 0x31, 0xFF),
        )

    def interpret_response(self, data):
        raw_response = SensirionI2cCommand.interpret_response(self, data)
        #return str(raw_response.decode('utf-8').rstrip('\0'))
        return raw_response


class MyI2cCmdReadMeasuredValues(SensirionI2cCommand):
    def __init__(self):
        super(MyI2cCmdReadMeasuredValues, self).__init__(
            command=0x0300,
            tx_data=[],
            rx_length=60,
            read_delay=0.05,
            timeout=0,
            crc=CrcCalculator(8, 0x31, 0xFF),
        )

    def interpret_response(self, data):
        raw_response = SensirionI2cCommand.interpret_response(self, data)
        return raw_response
#        return str(raw_response.decode('utf-8').rstrip('\0'))


# Implement a device
class sps30(I2cDevice):
    def __init__(self, connection, slave_address=0x69):
        super(sps30, self).__init__(connection, slave_address)

    def read_serial_number(self):
        return self.execute(MyI2cCmdReadSerialNumber())

    def start_measurement(self):
        return self.execute(MyI2cCmdStartMeasurement())

    def read_measured_values(self):
        return self.execute(MyI2cCmdReadMeasuredValues())


# Usage
with LinuxI2cTransceiver('/dev/i2c-1') as transceiver:
    device = sps30(I2cConnection(transceiver))
    print("Serial number: {}".format(device.read_serial_number()))

    print("Start measurement: {}".format(device.start_measurement()))
    
    print("Read measured values: {}".format(device.read_measured_values()))

    print("Serial number: {}".format(device.read_serial_number()))
