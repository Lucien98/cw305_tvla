import ctypes
from picosdk.ps6000 import ps6000 as ps
import numpy as np
import matplotlib.pyplot as plt
from picosdk.functions import adc2mV, assert_pico_ok, mV2adc
from utils.classes import Singleton

class PicoScope(metaclass=Singleton):
	"""this is the simplied and modified class of lecroy_interface"""
	def __init__(self, preTrigger, nsamples, nbatch):
		# Create chandle and status ready for use
		self.status = {}
		self.chandle = ctypes.c_int16()
		# self.args = args

		# Opens the device/s
		self.status["openunit"] = ps.ps6000OpenUnit(ctypes.byref(self.chandle), None)
		assert_pico_ok(self.status["openunit"])

		# Displays the serial number and handle
		print(self.chandle.value)
		# todo: disable all channels

		# Setting the number of sample to be collected
		self.preTriggerSamples = preTrigger # int(args.nsamples / 2)
		self.postTriggerSamples = nsamples #int(args.nsamples / 2)
		self.maxsamples = self.preTriggerSamples + self.postTriggerSamples
		self.buffer = [(ctypes.c_int16 * self.maxsamples)() for i in range(nbatch)]
		self.triggerbuf = [(ctypes.c_int16 * self.maxsamples)() for i in range(nbatch)]

	def setupDataChannel(self, order, args):
		# Set up channel B
		# handle = chandle
		# channel = ps6000_CHANNEL_B = 0
		# enabled = 1
		# coupling type = ps6000_DC = 1
		# range = ps6000_50mV
		# analogue offset = 0 V
		# chBRange = 8
		if order == 1:
			self.status["setChB"] = ps.ps6000SetChannel(self.chandle, 1, 1, ps.PS6000_COUPLING["PS6000_DC_50R"], ps.PS6000_RANGE['PS6000_200MV'], 0, 0)
		if order == 2 and args.design == "noia41":
			self.status["setChB"] = ps.ps6000SetChannel(self.chandle, 1, 1, ps.PS6000_COUPLING["PS6000_DC_50R"], ps.PS6000_RANGE['PS6000_500MV'], 0, 0)
		if order == 2 and args.design == "pini41":
			self.status["setChB"] = ps.ps6000SetChannel(self.chandle, 1, 1, ps.PS6000_COUPLING["PS6000_DC_50R"], ps.PS6000_RANGE['PS6000_1V'], 0, 0)
		# assert_pico_ok(self.status["setChB"])
		# self.status["setChA"] = ps.ps6000SetChannel(self.chandle, 0, 0, ps.PS6000_COUPLING["PS6000_DC_50R"], ps.PS6000_RANGE['PS6000_5V'], 0, 0)
		# assert_pico_ok(self.status["setChA"])

		# self.status["setChC"] = ps.ps6000SetChannel(self.chandle, 2, 0, ps.PS6000_COUPLING["PS6000_DC_50R"], ps.PS6000_RANGE['PS6000_5V'], 0, 0)
		# assert_pico_ok(self.status["setChC"])
		# self.status["setChD"] = ps.ps6000SetChannel(self.chandle, 3, 0, ps.PS6000_COUPLING["PS6000_DC_50R"], ps.PS6000_RANGE['PS6000_5V'], 0, 0)
		# assert_pico_ok(self.status["setChD"])

	def setupTriggerChannel(self):
		chARange = 8
		self.status["setChA"] = ps.ps6000SetChannel(self.chandle, 0, 1, 1, ps.PS6000_RANGE['PS6000_5V'], 0, 0)
		assert_pico_ok(self.status["setChA"])
		# todo: need to enable it? -> answer: it seems the parameters
		# todo: we should setsimpletrigger for each rapidblock acquistion?
		# Sets up single trigger
		# Handle = Chandle
		# Enable = 1
		# Source = ps6000_channel_A = 0
		# Threshold = 1024 ADC counts
		# Direction = ps6000_Falling = 3
		# Delay = 0
		# autoTrigger_ms = 1000 : autoTrigger_ms: the number of milliseconds the device will wait if no trigger occurs.
		maxADC = ctypes.c_int16(32512)
		threshold = mV2adc(2000, ps.PS6000_RANGE['PS6000_5V'], maxADC)

		self.status["trigger"] = ps.ps6000SetSimpleTrigger(self.chandle, 1, 0, threshold, 3, 0, 1000)
		assert_pico_ok(self.status["setChA"])

	def setupTrigger(self):
		# Set up window pulse width trigger on A
		triggerConditions = ps.PS6000_TRIGGER_CONDITIONS(
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_TRUE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
			ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"])
		nTriggerConditions = 1

		self.status["setTriggerChannelConditions"] = ps.ps6000SetTriggerChannelConditions(self.chandle, ctypes.byref(triggerConditions), nTriggerConditions)
		assert_pico_ok(self.status["setTriggerChannelConditions"])

		self.status["setTriggerChannelDirections"] = ps.ps6000SetTriggerChannelDirections(
			self.chandle, 
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_INSIDE"], 
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"],
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"], 
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"], 
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"],
			ps.PS6000_THRESHOLD_DIRECTION["PS6000_NONE"])
		assert_pico_ok(self.status["setTriggerChannelDirections"])

		maxADC = ctypes.c_int16(32512)
		threshold = mV2adc(109.2, ps.PS6000_RANGE['PS6000_5V'], maxADC)
		hysteresis = mV2adc((109.2 * 0.015), ps.PS6000_RANGE['PS6000_5V'], maxADC)
		channelProperties = ps.PS6000_TRIGGER_CHANNEL_PROPERTIES(threshold,
																hysteresis,
																(threshold * -1),
																hysteresis,
																ps.PS6000_CHANNEL["PS6000_CHANNEL_A"],
																ps.PS6000_THRESHOLD_MODE["PS6000_WINDOW"])
																# ps.PS6000_THRESHOLD_MODE["PS6000_LEVEL"])
		nChannelProperties = 1
		auxOutputEnable = 0
		autoTriggerMilliseconds = 10000
		self.status["setTriggerChannelProperties"] = ps.ps6000SetTriggerChannelProperties(self.chandle, ctypes.byref(channelProperties), nChannelProperties, auxOutputEnable, autoTriggerMilliseconds)
		assert_pico_ok(self.status["setTriggerChannelProperties"])

		pwqConditions = ps.PS6000_PWQ_CONDITIONS(ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_TRUE"],
												ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
												ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
												ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
												ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"],
												ps.PS6000_TRIGGER_STATE["PS6000_CONDITION_DONT_CARE"])
		nPwqConditions = 1
		direction = ps.PS6000_THRESHOLD_DIRECTION["PS6000_FALLING"]
		upper = 0 #390625 #samples at timebase 8 is 10 ms
		lower = upper
		type = ps.PS6000_PULSE_WIDTH_TYPE["PS6000_PW_TYPE_GREATER_THAN"]
		self.status["setPulseWidthQualifier"] = ps.ps6000SetPulseWidthQualifier(self.chandle, ctypes.byref(pwqConditions), nPwqConditions, direction, lower, upper, type)
		assert_pico_ok(self.status["setPulseWidthQualifier"])

	def setupTimeBase(self):
		# Gets timebase innfomation
		# Warning: When using this example it may not be possible to access all Timebases as all channels are enabled by default when opening the scope.  
		# To access these Timebases, set any unused analogue channels to off.
		# Handle = chandle
		# Timebase = 2 = timebase
		# Nosample = maxsamples
		# TimeIntervalNanoseconds = ctypes.byref(timeIntervalns)
		# MaxSamples = ctypes.byref(returnedMaxSamples)
		# Segement index = 0
		self.timebase = 2
		timeIntervalns = ctypes.c_float()
		returnedMaxSamples = ctypes.c_int16()
		self.status["GetTimebase"] = ps.ps6000GetTimebase2(self.chandle, self.timebase, self.maxsamples, ctypes.byref(timeIntervalns), 1, ctypes.byref(returnedMaxSamples), 0)
		assert_pico_ok(self.status["GetTimebase"])

	def setupSeqmode(self, nbatch):
		# Creates converted types maxsamples
		cmaxSamples = ctypes.c_int32(self.maxsamples)

		# Handle = Chandle
		self.nSegments = nbatch
		# nMaxSamples = ctypes.byref(cmaxSamples)

		self.status["MemorySegments"] = ps.ps6000MemorySegments(self.chandle, self.nSegments, ctypes.byref(cmaxSamples))
		assert_pico_ok(self.status["MemorySegments"])

		# sets number of captures
		self.status["SetNoOfCaptures"] = ps.ps6000SetNoOfCaptures(self.chandle, self.nSegments)
		assert_pico_ok(self.status["SetNoOfCaptures"])

	def runBlock(self):
		# Starts the block capture
		# Handle = chandle
		# Number of prTriggerSamples
		# Number of postTriggerSamples
		# Timebase = 2 = 4ns (see Programmer's guide for more information on timebases)
		# time indisposed ms = None (This is not needed within the example)
		# Segment index = 0
		# LpRead = None
		# pParameter = None
		self.status["runblock"] = ps.ps6000RunBlock(self.chandle, self.preTriggerSamples, self.postTriggerSamples, self.timebase, 1, None, 0, None, None)
		assert_pico_ok(self.status["runblock"])

	def setupBuffer(self):
		for i in range(self.nSegments):

			# Create buffers ready for assigning pointers for data collection
			# bufferAMax = (ctypes.c_int16 * self.maxsamples)()
			# self.buffer[i] = (ctypes.c_int16 * self.maxsamples)()
			# bufferAMin = (ctypes.c_int16 * self.maxsamples)() # used for downsampling which isn't in the scope of this example

			# self.buffer.append(bufferAMax)
			# print(type(bufferAMax))
			# exit()
			# Setting the data buffer location for data collection from channel A
			# Handle = Chandle
			# source = ps6000_channel_A = 0
			# Buffer max = ctypes.byref(bufferAMax)
			# Buffer min = ctypes.byref(bufferAMin)
			# Buffer length = maxsamples
			# Segment index = 0
			# Ratio mode = ps6000_Ratio_Mode_None = 0
			self.status["SetDataBuffersRapid"] = ps.ps6000SetDataBufferBulk(self.chandle, 1, ctypes.byref(self.buffer[i]), self.maxsamples, i, 0)
			self.status["SetTriggerBuffersRapid"] = ps.ps6000SetDataBufferBulk(self.chandle, 0, ctypes.byref(self.triggerbuf[i]), self.maxsamples, i, 0)
			assert_pico_ok(self.status["SetDataBuffersRapid"])
			assert_pico_ok(self.status["SetTriggerBuffersRapid"])

	def receiveData(self):
		# Creates a overlow location for data
		overflow = (ctypes.c_int16 * self.nSegments)()
		# Creates converted types maxsamples
		cmaxSamples = ctypes.c_int32(self.maxsamples)

		# Checks data collection to finish the capture
		ready = ctypes.c_int16(0)
		check = ctypes.c_int16(0)
		while ready.value == check.value:
		    self.status["isReady"] = ps.ps6000IsReady(self.chandle, ctypes.byref(ready))

		# Handle = chandle
		# noOfSamples = ctypes.byref(cmaxSamples)
		# fromSegmentIndex = 0
		# ToSegmentIndex = 9
		# DownSampleRatio = 0
		# DownSampleRatioMode = 0
		# Overflow = ctypes.byref(overflow)
		# self.setupBuffer()
		# import time
		# time.sleep(1)
		self.status["GetValuesRapid"] = ps.ps6000GetValuesBulk(self.chandle, ctypes.byref(cmaxSamples), 0, self.nSegments-1, 0, 0, ctypes.byref(overflow))
		assert_pico_ok(self.status["GetValuesRapid"])
		for i in range(self.nSegments):
			if overflow[i] != 0: print(f"{0}-th data overflow!", i)
		return self.buffer, self.triggerbuf

	def get_trig_offsets(self):
		Times = (ctypes.c_int64 * self.nSegments)()
		TimeUnits = (ctypes.c_int64 * self.nSegments)()
		self.status[
			"GetValuesTriggerTimeOffsetBulk"
		] = ps.ps6000GetValuesTriggerTimeOffsetBulk64(
			self.chandle, ctypes.byref(Times), ctypes.byref(
				TimeUnits), 0, self.nSegments - 1
		)
		assert_pico_ok(self.status["GetValuesTriggerTimeOffsetBulk"])
		trig_offsets = np.array(Times)
		return trig_offsets


	def close(self):
		# Stops the scope
		# Handle = chandle
		self.status["stop"] = ps.ps6000Stop(self.chandle)
		assert_pico_ok(self.status["stop"])

		# Closes the unit
		# Handle = chandle
		self.status["close"] = ps.ps6000CloseUnit(self.chandle)
		assert_pico_ok(self.status["close"])

		# Displays the staus returns
		print(self.status)


