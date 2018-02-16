#!/usr/bin/python

import time
import Adafruit_ADS1x15
import numpy as np
import thingspeak
import smtplib
import traceback
import sys

##############################
# configuration
##############################
FREQ=5             # polling frequency, in seconds
THRESH_OK=60       # temperature under which to clear the low alarm
THRESH_LO=45       # temperature too low threshold
THRESH_FLT_LO=-20  # temperature fault low threshold
THRESH_FLT_HI=120  # temperature fault high threshold

##############################
# notification e-mail function
##############################

SMTP_USER='hutorski@gmail.com'
SMTP_PASS='lovimbaboch3k'
SMTP_SERV='smtp.gmail.com'

def notify(short_msg, subject):
    try:
        server = smtplib.SMTP(SMTP_SERV, 587)
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)

        to_list = ['hutorski@gmail.com']
        body = short_msg

        message = """\From: %s\nTo: %s\nSubject: %s\n\n%s""" % (SMTP_USER, ", ".join(to_list), subject, body)

        if len(to_list) > 0:
            server.sendmail(SMTP_USER, to_list, message)

        server.close()
        
    except:
        print ""
        print "Non-fatal error sending notification e-mail. Error details:"
        print ""
        traceback.print_exc()

class do_tee(object):
    def __init__(self, name, mode='a'):
        self.file = open(name, mode)
        self.stdout = sys.stdout
        sys.stdout = self
    def __del__(self):
        self.file.close()
    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)

###############
# main funciton
###############

do_tee('/home/pi/thermostat/thermo_log.txt')

ch = thingspeak.Channel(360631, 'DLV7TX0MNHS7VN72', 'OXEC4F47O82ZOHWE')

adc = Adafruit_ADS1x15.ADS1115()

# Note you can change the I2C address from its default (0x48), and/or the I2C
# bus by passing in these optional parameters:
#adc = Adafruit_ADS1x15.ADS1015(address=0x49, busnum=1)

# Choose a gain of 1 for reading voltages from 0 to 4.09V.
# Or pick a different gain to change the range of voltages that are read:
#  - 2/3 = +/-6.144V
#  -   1 = +/-4.096V
#  -   2 = +/-2.048V
#  -   4 = +/-1.024V
#  -   8 = +/-0.512V
#  -  16 = +/-0.256V
# See table 3 in the ADS1015/ADS1115 datasheet for more info on gain.

# circuit and ADC configuration
GAIN = 1         # ADC gain
RES  = 12032     # measured first stage resistor value
VREF = 4.096     # full swing of ADC
VDD  = 3.3       # voltage driving the circuit

# 3rd-degree polyfit of resistance to temperature
# based on calibration data in calib.txt
PFIT = np.array([ -5.45255673e-12,
                   3.91963869e-07,
                  -1.06683972e-02,
                  1.48293118e+02])

# current condition
# 0 - normal
# 1 - temperature too low
# 2 - fault
cond = 0


# now run the loop
while True:
    
    # read channel 0
    dac = adc.read_adc(0, gain=GAIN)
    v   = dac / 32768.0 * VREF
    if v > VDD:
        v = VDD-0.001

    # convert to resistance
    res = ((v/VDD)*RES) / (1-v/VDD)

    # temperature
    temp = np.polyval(PFIT, res)
    if temp < -460:
        temp = -460

    # timestamp
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    print ts, 'dac=%d, v=%.3f, res=%d temp=%dF' % (dac, v, res, temp)
    try:
	ch.update({'field1' : temp })	
    except:
        print 'Error uploading the data'

    # check for conditions
    if cond == 0:
        if temp < THRESH_FLT_LO or temp > THRESH_FLT_HI:
            print 'Detected fault'
            notify('Temperature measured at %d degrees' % temp, 'Hot Tub Measurement Fault')
            cond = 2
        elif temp < THRESH_LO:
            print 'Detected low temperature'
            notify('Temperature measured at %d degrees' % temp, 'Hot Tub Temperature Low')
            cond = 1
            
    elif cond == 2 and temp > THRESH_FLT_LO and temp < THRESH_FLT_HI:
        print 'Detected fault clearing'
        notify('Temperature measured at %d degrees' % temp, 'Hot Tub Fault Cleared')
        cond = 0
        
    elif cond == 1 and temp > THRESH_OK:
        print 'Detected temperature restored back to normal'
        notify('Temperature measured at %d degrees' % temp, 'Hot Tub Temperature Restored')
        cond = 0            
    
    time.sleep(FREQ)
    
    
