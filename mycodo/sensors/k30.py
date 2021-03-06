# coding=utf-8

from lockfile import LockFile
import logging
import serial
import time
import RPi.GPIO as GPIO
from .base_sensor import AbstractSensor

logger = logging.getLogger("mycodo.sensors.k30")
K30_LOCK_FILE = "/var/lock/sensor-k30"


class K30Sensor(AbstractSensor):
    """ A sensor support class that monitors the K30's CO2 concentration """

    def __init__(self):
        super(K30Sensor, self).__init__()
        self._co2 = 0
        if GPIO.RPI_INFO['P1_REVISION'] == 3:
            self.serial_device = "/dev/ttyS0"
        else:
            self.serial_device = "/dev/ttyAMA0"

    def __repr__(self):
        """  Representation of object """
        return "<{cls}(co2={co2})>".format(
            cls=type(self).__name__,
            co2="{0:.2f}".format(self._co2))

    def __str__(self):
        """ Return CO2 information """
        return "CO2: {co2}".format(co2="{0:.2f}".format(self._co2))

    def __iter__(self):  # must return an iterator
        """ K30 iterates through live CO2 readings """
        return self

    def next(self):
        """ Get next CO2 reading """
        if self.read():  # raised an error
            raise StopIteration  # required
        return dict(co2=float('{0:.2f}'.format(self._co2)))

    def info(self):
        conditions_measured = [
            ("CO2", "co2", "float", "0.00", self._co2, self.co2)
        ]
        return conditions_measured

    @property
    def co2(self):
        """ CO2 concentration in ppmv """
        if not self._co2:  # update if needed
            self.read()
        return self._co2

    def get_measurement(self):
        """ Gets the K30's CO2 concentration in ppmv via UART"""
        ser = serial.Serial(self.serial_device, timeout=1)  # Wait 1 second for reply
        ser.flushInput()
        time.sleep(1)
        ser.write("\xFE\x44\x00\x08\x02\x9F\x25")
        time.sleep(.01)
        resp = ser.read(7)
        if len(resp) == 0:
            co2 = None
        else:
            high = ord(resp[3])
            low = ord(resp[4])
            co2 = (high * 256) + low
        return co2

    def read(self):
        """
        Takes a reading from the K30 and updates the self._co2 value

        :returns: None on success or 1 on error
        """
        lock = LockFile(K30_LOCK_FILE)
        try:
            # Acquire lock on K30 to ensure more than one read isn't
            # being attempted at once.
            while not lock.i_am_locking():
                try:
                    lock.acquire(timeout=60)  # wait up to 60 seconds before breaking lock
                except Exception as e:
                    logger.error("{cls} 60 second timeout, {lock} lock broken: "
                                 "{err}".format(cls=type(self).__name__,
                                                lock=K30_LOCK_FILE,
                                                err=e))
                    lock.break_lock()
                    lock.acquire()
            self._co2 = self.get_measurement()
            lock.release()
            if self._co2 is None:
                return 1
            return  # success - no errors
        except Exception as e:
            logger.error("{cls} raised an exception when taking a reading: "
                         "{err}".format(cls=type(self).__name__, err=e))
            lock.release()
            return 1
