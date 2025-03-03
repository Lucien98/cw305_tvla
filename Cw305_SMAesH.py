#!/usr/bin/env python3

from scalib.metrics import Ttest, MTtest
import chipwhisperer as cw
import ctypes
import numpy as np
from picosdk.ps6000 import ps6000 as ps
from picosdk.functions import adc2mV, assert_pico_ok, mV2adc
import chipwhisperer as cw
import time
from Cryptodome.Cipher import AES
import argparse
import re
from datetime import datetime
from chipwhisperer.capture.targets.CW305 import CW305


ranges_mV = {
    10: 0,
    20: 1,
    50: 2,
    100: 3,
    200: 4,
    500: 5,
    1000: 6,
    2000: 7,
    5000: 8, 
    10000: 9,
    20000: 10,
    50000: 11,
    100000: 12,
    200000: 13,
}


# target = cw.target(\
#     None,\
#     cw.targets.CW305,\
#     bsfile="cw305_opt.bit", \
#     force=True,\
# )

# target = cw.target(None, cw.targets.CW305)#, bsfile="./cw305_opt.bit", force=True
bitstream_path = "E:/2025/SMAesH-challenge/fpga_designs/SMAesH/cw305_ucg_target/cw305_ucg_target.runs/impl_1/cw305_top.bit"
target = CW305()
target.con(bsfile=bitstream_path, force=True)
print(bitstream_path)

# f = open("cw305_defines.v")
# for l in f:
#     if re.match("^`define [^ ]*[ ]*'h[\d|a-f][\d|a-f]", l):
#         l = l.split(" ")
#         k,v = l[1],l[-1]
#         v = int(v[2:],16)
#         globals()[k] = v
# f.close()

parser = argparse.ArgumentParser()
parser.add_argument('--with-trigger', action='store_true')
parser.add_argument('--store-traces', action='store_true')
parser.add_argument('--univ-ttest', action='store_true')
args = parser.parse_args()


# target.vccint_set(1.0)

# we only need PLL1:
# target.pll.pll_enable_set(True)
# target.pll.pll_outenable_set(True, 0)
# target.pll.pll_outenable_set(True, 1)
# target.pll.pll_outenable_set(False, 2)

# FpgaClkFreq=1.5625E6*6
# target.pll.pll_outfreq_set(FpgaClkFreq, 1)
# target.pll.pll_outfreq_set(10e6, 0)

# 1ms is plenty of idling time
target.clkusbautooff = True
target.clksleeptime = 1

ORDER = 1

# key = [0x21, 0xef, 0x78, 0x01, \
#        0x43, 0xbe, 0x56, 0xef, \
#        0x65, 0xad, 0x34, 0xcd, \
#        0x87, 0xde, 0x12, 0xab]

# key_0 = [np.random.randint(0,256) for i in range(0,16)]
# key_1 = [np.random.randint(0,256) for i in range(0,16)]
# key_2 = [key_0[i]^key_1[i]^key[i] for i in range(0,16)]

# target.fpga_write(REG_CRYPT_KEY_0, bytearray(reversed(key_0)))
# target.fpga_write(REG_CRYPT_KEY_1, bytearray(reversed(key_1)))
# target.fpga_write(REG_CRYPT_KEY_2, bytearray(reversed(key_2)))
# time.sleep(0.001)
def printBytes(info, data):
    n = len(data)*2
    data = hex(int.from_bytes(data, 'big')).upper()
    data = re.sub(r'(.{16})', r'\1 ', data[2:].rjust(n,"0"))
    print("%s%s" %(info, data))

def xorbytes(b, order):
    # sh: shares of data
    sh = [[] for i in range(order + 1)]
    for i in range(order+1):
        sh[i] = b[i*16:(i+1)*16]
    # b: the original value
    b = [0 for i in range(16)]
    for i in range(16):
        for j in range(order+1):
            b[i] = b[i] ^ sh[j][i]
    return bytes(b)

def get_umsk_data(data, order):
    data_little = xorbytes(data, order)
    data_big = bytes(data_little)
    return data_big

def setup_pico(num_measures, preTrigger, postTrigger):
    # Create chandle and status ready for use
    chandle = ctypes.c_int16()
    status = {}
    ps.ps6000CloseUnit(chandle)
    
    ############## Step 1 #####################
    # Open the oscilloscope using ps6000OpenUnit.
    status["openunit"] = ps.ps6000OpenUnit(ctypes.byref(chandle), None)
    assert_pico_ok(status["openunit"])

    ############## Step 2 #####################
    # Select channel ranges and AC/DC coupling using ps6000SetChannel.
    ch_a_range = ranges_mV[50]
    status["setChA"] = ps.ps6000SetChannel(chandle, 0, 1, 1, ch_a_range, 0, 2)
    assert_pico_ok(status["setChA"])

    ch_b_range = ranges_mV[5000]
    status["setChB"] = ps.ps6000SetChannel(chandle, 1, 1, 0, ch_b_range, 0, 0)
    assert_pico_ok(status["setChB"])

    # status["SetExternalClock"] = ps.ps6000SetExternalClock(chandle, 2, 200)
    # print(status["SetExternalClock"])
    # assert_pico_ok(status["SetExternalClock"])

    ############## Step 3 #####################
    # Set the number of memory segments equal to or greater than the number of captures required using ps6000MemorySegments. Use ps6000SetNoOfCaptures before each run to specify the number of waveforms to capture.
    maxSamples = preTrigger + postTrigger
    cmaxSamples = ctypes.c_int32(maxSamples)
    status["MemorySegments"] = ps.ps6000MemorySegments(
        chandle, num_measures, ctypes.byref(cmaxSamples)
    )
    assert_pico_ok(status["MemorySegments"])

    status["SetNoOfCaptures"] = ps.ps6000SetNoOfCaptures(chandle, num_measures)
    assert_pico_ok(status["SetNoOfCaptures"])

    ############## Step 4 #####################
    # Using ps6000GetTimebase, select timebases until the required nanoseconds per sample is located.

    timebase = 3
    timeIntervalns = ctypes.c_float()
    returnedMaxSamples = ctypes.c_int32()
    status["getTimebase2"] = ps.ps6000GetTimebase2(
        chandle,
        timebase,
        maxSamples,
        ctypes.byref(timeIntervalns),
        1,
        ctypes.byref(returnedMaxSamples),
        0,
    )
    assert_pico_ok(status["getTimebase2"])

    ############## Step 5 #####################
    # Use the trigger setup functions ps6000SetTriggerChannelConditions, ps6000SetTriggerChannelDirections and ps6000SetTriggerChannelProperties to set up the trigger if required.
    threshold_adc = int(mV2adc(1000, ch_b_range, ctypes.c_int16(32512)))
    print(threshold_adc)
    status["trigger"] = ps.ps6000SetSimpleTrigger(
        chandle, 1, 1, threshold_adc, 2, 0, 100000
    )
    assert_pico_ok(status["trigger"])


    ############## Step 8 #####################
    # Use ps6000SetDataBufferBulk to tell the driver where your memory buffers are. Call the function once for each channel/segment combination for which you require data. For greater efficiency with multiple captures, you could do this outside the loop after step 5.
    ntraces = num_measures
    global bufferAMax
    global bufferBMax
    global bufferAMin
    global bufferBMin
    bufferAMax = []
    bufferAMin = []
    bufferBMax = []
    bufferBMin = []

    for i in range(ntraces):
        bufferAMax.append((ctypes.c_int16 * maxSamples)())
        bufferAMin.append((ctypes.c_int16 * maxSamples)())
        status["SetDataBuffersBulk"] = ps.ps6000SetDataBuffersBulk(
            chandle,
            0,
            ctypes.byref(bufferAMax[i]),
            ctypes.byref(bufferAMin[i]),
            maxSamples,
            i,
            0,
        )
        assert_pico_ok(status["SetDataBuffersBulk"])

        if args.with_trigger:
            bufferBMax.append((ctypes.c_int16 * maxSamples)())
            bufferBMin.append((ctypes.c_int16 * maxSamples)())
            status["SetDataBuffersBulk"] = ps.ps6000SetDataBuffersBulk(
                chandle,
                1,
                ctypes.byref(bufferBMax[i]),
                ctypes.byref(bufferBMin[i]),
                maxSamples,
                i,
                0,
            )
        assert_pico_ok(status["SetDataBuffersBulk"])
    overflow = (ctypes.c_int64 * num_measures)()
    ready = ctypes.c_int16(0)
    check = ctypes.c_int16(0)


    return chandle, cmaxSamples, timebase

def batchRun():
	key_used,pt_used,state_used = target.batchRun(nbatch, nstate, init_key, init_pt, flags_key, flags_pt, refreshes)#, seed=seed
	time.sleep(3.4)
	last_ct_shares = target.readOutput()
	last_ct_shares = bytes(last_ct_shares)
	last_ct = xorbytes(last_ct_shares, 1)
	# printBytes("last_ct_shares = ", bytes(reversed(last_ct_shares)))
	# printBytes("last_ct = ", last_ct)
	# printBytes("last_key_used = ", bytes(reversed(key_used[-1])))
	# printBytes("last_pt_used = ", bytes(reversed(pt_used[-1])))


	sh_key = bytes(key_used[-1])
	sh_plaintext = bytes(pt_used[-1,10:])
	umsk_key = get_umsk_data(sh_key, ORDER)
	cipher = AES.new(umsk_key, AES.MODE_ECB)
	umsk_plaintext = get_umsk_data(sh_plaintext, ORDER)
	umsk_ciphertext = cipher.encrypt(umsk_plaintext)

	sh_ciphertext = bytes(last_ct_shares)
	hw_ciphertext = get_umsk_data(sh_ciphertext, ORDER)

	# printBytes("ciphertext from hardware: ", hw_ciphertext)
	# printBytes("ciphertext from local:    ", umsk_ciphertext)
	# printBytes("plaintext from local:    ", umsk_plaintext)
	# printBytes("key from local:    ", umsk_key)
	# assert hw_ciphertext == umsk_ciphertext
	if hw_ciphertext != umsk_ciphertext:
		with open("a.txt", "a") as f:
			f.write("error")
	return state_used



def get_measurements(num_measures, preTrigger, postTrigger, chandle, cmaxSamples, timebase):
    status = {}
    ############## Step 0 #####################
    # X = np.random.randint(0,2,num_measures,dtype=np.uint16)
    # pt_0 = []
    # pt_1 = []
    # pt_2 = []
    # for nti in range(0, num_measures):
    #     fixed = X[nti]
    #     if fixed:
    #         pt1 = [np.random.randint(0, 256) for i in range(0,16)]
    #         pt2 = [np.random.randint(0, 256) for i in range(0,16)]
    #         pt0 = [pt1[i] ^ pt2[i] for i in range(0,16)]
    #     else:
    #         pt0 = [np.random.randint(0, 256) for i in range(0,16)]
    #         pt1 = [np.random.randint(0, 256) for i in range(0,16)]
    #         pt2 = [np.random.randint(0, 256) for i in range(0,16)]
    #     pt_0.append(pt0)
    #     pt_1.append(pt1)
    #     pt_2.append(pt2)
    # key = [0x21, 0xef, 0x78, 0x01, \
    #    0x43, 0xbe, 0x56, 0xef, \
    #    0x65, 0xad, 0x34, 0xcd, \
    #    0x87, 0xde, 0x12, 0xab]
    ############## Step 6 #####################
    # Start the oscilloscope running using ps6000RunBlock.
    status["runBlock"] = ps.ps6000RunBlock(
        chandle, preTrigger, postTrigger, timebase, 0, None, 0, None, None
    )
    assert_pico_ok(status["runBlock"])
    time.sleep(1)
    overflow = (ctypes.c_int64 * num_measures)()
    ready = ctypes.c_int16(0)
    check = ctypes.c_int16(0)

    ############## Step 7 #####################
    # Wait until the oscilloscope is ready using the ps6000BlockReady callback.
    # print(2)
    state_used = batchRun()
    while ready.value == check.value:
        status["isReady"] = ps.ps6000IsReady(chandle, ctypes.byref(ready))

    ############## Step 9 #####################
    # Transfer the blocks of data from the oscilloscope using ps6000GetValuesBulk.
    status["GetValuesBulk"] = ps.ps6000GetValuesBulk(
        chandle,
        ctypes.byref(cmaxSamples),
        0,
        num_measures - 1,
        0,
        0,
        ctypes.byref(overflow),
    )
    assert_pico_ok(status["GetValuesBulk"])

    ############# Step 10 ######################
    # Retrieve the time offset for each data segment using ps6000GetValuesTriggerTimeOffsetBulk64.
    Times = (ctypes.c_int64 * num_measures)()
    TimeUnits = (ctypes.c_int64 * num_measures)()
    status[
        "GetValuesTriggerTimeOffsetBulk"
    ] = ps.ps6000GetValuesTriggerTimeOffsetBulk64(
        chandle, ctypes.byref(Times), ctypes.byref(
            TimeUnits), 0, num_measures - 1
    )
    assert_pico_ok(status["GetValuesTriggerTimeOffsetBulk"])
    trig_offsets = np.array(Times)
    ############# Step 11 ######################
    # Display the data.

    ############# Step 12 ######################
    # Repeat steps 6 to 11 if necessary.

    ############# Step 13 ######################
    status["stop"] = ps.ps6000Stop(chandle)
    assert_pico_ok(status["stop"])
    
    assert(timebase == 3) #Otherwise trace alignment is destroyed.
    data = np.array(bufferAMax, dtype=np.int16)
    shifted = 0
    for i in range(0, num_measures):
    	if (trig_offsets[i]//1000) > 800:
    	    data[i] = np.roll(data[i], 1)
    	    shifted += 1
    print("Shifted: %d"%shifted)
    if args.with_trigger:
        trigger = np.array(bufferBMax, dtype=np.int16)
        for i in range(0, num_measures):
    	    if (trig_offsets[i]//1000) > 800:
    	        trigger[i] = np.roll(trigger[i], 1)

    if args.with_trigger:
        return data, trigger, state_used.astype(np.uint16).ravel() # X
    else:
        return data, None, state_used.astype(np.uint16).ravel() # X


# N = 40            # traces per block
# M = 1             # number of blocks
# plot_delta = 40
N = 5000            # traces per block
M = 20000             # number of blocks
plot_delta = 40000
preTrigger  = 10 # samples to record BEFORE trigger
num_traces = 0

nbatch = N
nstate = 2
init_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
init_pt=np.zeros([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)
flags_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
# plaintext are all random
flags_pt=np.ones([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)
refreshes=[]
# random key, fixed key is configured in flags_key[0,:]
if nstate != 1:
    flags_key[1,:] = 1

# seed=0xd8fdc297
for i in range(ORDER):
    if nstate == 1: break
    for j in range(16):
        refreshes.append([('k',16*i+j),('k',16*ORDER+j)])


# samples to record AFTER/WHILE trigger
if args.univ_ttest:
    postTrigger = 9000
else:
    postTrigger = 9000

chandle, cmaxSamples, timebase = setup_pico(N, preTrigger, postTrigger)
if args.univ_ttest:
    ttest = Ttest(d=3)#preTrigger+postTrigger,
else:
    num_samples = postTrigger + preTrigger
    samples_bi = (num_samples*(num_samples+1))//2
    pois = np.zeros((2,samples_bi),dtype=np.uint32)
    idx = 0
    for i in range(num_samples):
        for j in range(i,num_samples):
            pois[0,idx] = i
            pois[1,idx] = j
            idx+=1
    mttest = MTtest(d=2,pois=pois)

last_plot = 0

for _ in range(0, M):
    t1 = time.time()
    # print(1)
    data, trigger, X = get_measurements(N, preTrigger, postTrigger, chandle, cmaxSamples, timebase)

    if args.univ_ttest:
        ttest.fit_u(data, X)
    else:
        mttest.fit_u(data, X)
    num_traces += data.shape[0]
    format_num_traces = '{:,}'.format(num_traces).replace(",", "-")
    t2 = time.time()
    print("Fitted %s traces in %.2fs."%(format_num_traces, t2-t1))

    if args.store_traces:
        now = datetime.now()
        date_time = now.strftime("%m%d%Y_%H%M%S")

        with open("data/traces_%s.npy"%date_time, "wb") as f:
            np.save(f, data)

        if args.with_trigger:
            with open("data/trigger_%s.npy"%date_time, "wb") as f:
                np.save(f, trigger)

        with open("data/X_%s.npy"%date_time, "wb") as f:
            np.save(f, X)
        
        print("Saved traces to: ", "data/traces_%s.npy"%date_time)
        print("Trace set (N = %d) constructed in %.2fs"%(N, t2-t1))
    elif args.univ_ttest:
        print(num_traces, plot_delta, ((num_traces // plot_delta)), last_plot)
        if (num_traces // plot_delta) != last_plot:
            t = ttest.get_ttest()
            with open("data/ttest_uni_%s.npy"%format_num_traces, "wb") as f:
                np.save(f, t)
            print("Saved ttest results to: data/ttest_uni_%s.npy"%format_num_traces )
            last_plot = (num_traces // plot_delta)
    else:
        if (num_traces // plot_delta) != last_plot:
            mtt = mttest.get_ttest()
            print(mtt.shape)
            with open("data/ttest_bi_%s.npy"%format_num_traces, "wb") as f:
                np.save(f, mtt)
            print("Saved ttest results to: data/ttest_bi_%s.npy"%format_num_traces )
            last_plot = (num_traces // plot_delta)

############# Step 14 ######################
# Close unitDisconnect the scope
ps.ps6000CloseUnit(chandle)



