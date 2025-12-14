import time
import math
import re

try:
    import smbus
except ImportError:
    print("smbus not found. Using MockSMBus for testing.")
    class smbus:
        class SMBus:
            def __init__(self, bus):
                pass
            def write_byte_data(self, addr, reg, val):
                pass
            def read_byte_data(self, addr, reg):
                return 0

# ============================================================================
# Emakefun_I2C Implementation
# ============================================================================
class Emakefun_I2C(object):

  @staticmethod
  def getPiRevision():
    "Gets the version number of the Raspberry Pi board"
    try:
      with open('/proc/cpuinfo', 'r') as infile:
        for line in infile:
          match = re.match(r'Revision\s+:\s+.*(\w{4})$', line)
          if match and match.group(1) in ['0000', '0002', '0003']:
            return 1
          elif match:
            return 2
        return 0
    except:
      return 0

  @staticmethod
  def getPiI2CBusNumber():
    return 1 if Emakefun_I2C.getPiRevision() > 1 else 0

  def __init__(self, address, busnum=-1, debug=False):
    self.address = address
    self.bus = smbus.SMBus(busnum if busnum >= 0 else Emakefun_I2C.getPiI2CBusNumber())
    self.debug = debug

  def write8(self, reg, value):
    "Writes an 8-bit value to the specified register/address"
    try:
      self.bus.write_byte_data(self.address, reg, value)
    except IOError:
      print("Error accessing 0x%02X: Check your I2C address" % self.address)

  def readU8(self, reg):
    "Read an unsigned byte from the I2C device"
    try:
      result = self.bus.read_byte_data(self.address, reg)
      return result
    except IOError:
      print("Error accessing 0x%02X: Check your I2C address" % self.address)
      return -1


# ============================================================================
# PCA9685 Class (Equivalent to PWM class in Emakefun driver)
# ============================================================================
class PCA9685:
  # Registers/etc.
  __MODE1              = 0x00
  __MODE2              = 0x01
  __SUBADR1            = 0x02
  __SUBADR2            = 0x03
  __SUBADR3            = 0x04
  __PRESCALE           = 0xFE
  __LED0_ON_L          = 0x06
  __LED0_ON_H          = 0x07
  __LED0_OFF_L         = 0x08
  __LED0_OFF_H         = 0x09
  
  __ALL_LED_ON_L       = 0xFA
  __ALL_LED_ON_H       = 0xFB
  __ALL_LED_OFF_L      = 0xFC
  __ALL_LED_OFF_H      = 0xFD

  # Bits
  __RESTART            = 0x80
  __SLEEP              = 0x10
  __ALLCALL            = 0x01
  __INVRT              = 0x10
  __OUTDRV             = 0x04

  def __init__(self, address=0x40, debug=False):
    self.i2c = Emakefun_I2C(address)
    self.address = address
    self.debug = debug
    
    if (self.debug):
      print("Reseting PCA9685 MODE1 (without SLEEP) and MODE2")
      
    self.setAllPWM(0, 0)
    self.i2c.write8(self.__MODE2, self.__OUTDRV)
    self.i2c.write8(self.__MODE1, self.__ALLCALL)
    time.sleep(0.005) # wait for oscillator
    
    mode1 = self.i2c.readU8(self.__MODE1)
    mode1 = mode1 & ~self.__SLEEP # wake up (reset sleep)
    self.i2c.write8(self.__MODE1, mode1)
    time.sleep(0.005) # wait for oscillator

  def setPWMFreq(self, freq):
    "Sets the PWM frequency"
    prescaleval = 25000000.0    # 25MHz
    prescaleval /= 4096.0       # 12-bit
    prescaleval /= float(freq)
    prescaleval -= 1.0
    
    if (self.debug):
      print("Setting PWM frequency to %d Hz" % freq)
      print("Estimated pre-scale: %d" % prescaleval)
      
    prescale = math.floor(prescaleval + 0.5)
    
    oldmode = self.i2c.readU8(self.__MODE1)
    newmode = (oldmode & 0x7F) | 0x10 # sleep
    self.i2c.write8(self.__MODE1, newmode) # go to sleep
    self.i2c.write8(self.__PRESCALE, int(math.floor(prescale)))
    self.i2c.write8(self.__MODE1, oldmode)
    time.sleep(0.005)
    self.i2c.write8(self.__MODE1, oldmode | 0x80)

  def setPWM(self, channel, on, off):
    "Sets a single PWM channel"
    self.i2c.write8(self.__LED0_ON_L + 4 * channel, int(on) & 0xFF)
    self.i2c.write8(self.__LED0_ON_H + 4 * channel, int(on) >> 8)
    self.i2c.write8(self.__LED0_OFF_L + 4 * channel, int(off) & 0xFF)
    self.i2c.write8(self.__LED0_OFF_H + 4 * channel, int(off) >> 8)

  def setAllPWM(self, on, off):
    "Sets a all PWM channels"
    self.i2c.write8(self.__ALL_LED_ON_L, int(on) & 0xFF)
    self.i2c.write8(self.__ALL_LED_ON_H, int(on) >> 8)
    self.i2c.write8(self.__ALL_LED_OFF_L, int(off) & 0xFF)
    self.i2c.write8(self.__ALL_LED_OFF_H, int(off) >> 8)
