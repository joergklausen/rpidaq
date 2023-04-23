# rpidaq
Rasperry Pi Data acquisition for Air Quality monitoring

## Supported sensors
- [Sensirion SPS30](https://sensirion.com/media/documents/8600FF88/616542B5/Sensirion_PM_Sensors_Datasheet_SPS30.pdf)

## Basics
### Understand and configure the I2C bus
[ABelectronics.co.uk](https://www.abelectronics.co.uk/kb/article/1090/i2c-part-1---introducing-i2c) provides a nice introduction to I2C and how it can be used on the Raspberry Pi.

To enable I2C on the RPI, perform these steps:
1. From the Start menu >Preferences >Rasperry Pi Configuration >Interfaces >Enable I2C.
2. Reboot the RPI.

### Wiring the SPS30 to the RPI I2C bus 
#### SPS30 (cf. 3 Hardware Interface Specifications)
Looking at the connector of the SPS30, pin 1 is towards the middle of the case, pin 5 is to the far side.

Pin|Description|UART|I2C
--|--|--|--
1|Supply voltage 5V|VDD|VDD
2|UART receiving pin/ I2C serial data input/ output|RX|SDA
3|UART transmitting pin/ I2C serial clock input	TX|SCL
4|Interface select (UART: floating (NC) /I2C: GND)|NC|GND
5|Ground|GND|GND

#### I2C interface of the RPI
The I2C port on the Raspberry Pi uses GPIO2 (SDA) and GPIO3 (SCL) pins.

o-----------------------------------
|  2  4  6  8 10 12 14 ... 40
|  1  3  5  7  9 11 13 ... 39
| 
Pin 3: GPIO2 (SDA)
Pin 5: GPIO3 (SCL)

### Test the RPI I2C interface
1. Without any device connected to the I2C bus, open a terminal and type
    $ sudo i2cdetect -y 1

   This should return an empty matrix of 8 rows labeled 00 .. 70.

2. Connect the SPS30 to the RPI GPIO as follows and repeat step 1:

SPS30 Pin|GPIO Pin|Description
--|--|--
1|2|+5V
2|3|SDA
3|5|SCL
4|9|GND
5|9|GND

    This should return 

         0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
    00:          -- -- -- -- -- -- -- -- -- -- -- -- -- 
    10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
    20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
    30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
    40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
    50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
    60: -- -- -- -- -- -- -- -- -- 69 -- -- -- -- -- -- 
    70: -- -- -- -- -- -- -- -- 

### Set up environment in VS Code
1. Clone github repo
2. Ctrl+Shift+P >Create Environment >venv
3. Open terminal within VS Code, type
    $ . .venv/bin/activate
4. Install dependencies:
    $ pip install -r requirements.txt


### Example output
{
  "sensor_data": {
    "mass_density": {
      "pm1.0": 2.006,
      "pm2.5": 6.145,
      "pm4.0": 9.417,
      "pm10": 11.059
    },
    "particle_count": {
      "pm0.5": 2.942,
      "pm1.0": 11.156,
      "pm2.5": 15.114,
      "pm4.0": 15.956,
      "pm10": 16.18
    },
    "particle_size": 1.428,
    "mass_density_unit": "ug/m3",
    "particle_count_unit": "#/cm3",
    "particle_size_unit": "um"
  },
  "timestamp": 1678644087
}

## Setup DDNS
https://www.sdn46.com/setting-up-duckdns-on-your-raspberry-pi/
