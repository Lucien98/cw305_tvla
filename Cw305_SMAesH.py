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

import sys
sys.path.append('./board_interfaces')
sys.path.append('./library')
from pico_if import *

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

def parse_arguments():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--order', metavar='order', required=False, default=2,
                            help='program the firmware according to the order', type=int)
    # parser.add_argument('--initial_sharing', metavar='initial_sharing', required=False, default=2,
    #                         help='1: key and plaintext without initial sharing, for rngoff option; 2: both key and plaintext with initial sharing, it is the regular case.', type=int)
    parser.add_argument('--design', metavar='design', required=False, default='noia41',
                            help='possible values: noia41, noia51, pini41, pini51', type=str)
    parser.add_argument('--rngoff', action="store_true",
                            help='choose the bitsteam file with rng on')
    parser.add_argument('--sample-trace', action='store_true')
    parser.add_argument('--with-trigger', action='store_true')
    parser.add_argument('--store-traces', action='store_true')
    parser.add_argument('--univ-ttest', action='store_true')
    args = parser.parse_args()
    return args


args = parse_arguments()

ORDER = args.order
# normal frequency: 1.5625MHz, otherwise 10MHz
NORMAL_FRE = True
NORMAL_FRE = False

DOM = True

THREE_STAGED = True

# TV=True
TV=False

if args.sample_trace:
    args.with_trigger = True
    args.store_traces = True
    TV = True
print(TV)
bslocation=""
if args.rngoff:
    bslocation = args.design + "/" + "rngoff"
else:
    bslocation = args.design + "/" + "rngon"

if DOM:
    bitstream_path = "./bitstream/%s/cw305_top_o%d.bit" % ( bslocation, ORDER)
else:
    bitstream_path = "E:/2025/SMAesH-challenge/fpga_designs/SMAesH/cw305_ucg_target/cw305_ucg_target.runs/impl_1/cw305_top_trig_wrng_o%d.bit" % ORDER

target = CW305()
target.con(bsfile=bitstream_path, force=True)
print(bitstream_path)


# target.vccint_set(1.0)

# we only need PLL1:
# target.pll.pll_enable_set(True)
# target.pll.pll_outenable_set(True, 0)
# target.pll.pll_outenable_set(True, 1)
# target.pll.pll_outenable_set(False, 2)

if NORMAL_FRE:
    FpgaClkFreq=1.5625E6*6
    target.pll.pll_outfreq_set(FpgaClkFreq, 1)
    target.pll.pll_outfreq_set(10e6, 0)

# 1ms is plenty of idling time
target.clkusbautooff = True
target.clksleeptime = 1


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

def batchRun():
	key_used,pt_used,state_used = target.batchRun(nbatch, nstate, init_key, init_pt, flags_key, flags_pt, refreshes)#, seed=seed
	if ORDER == 1:
		time.sleep(3.4)
	if ORDER == 2:
		time.sleep(5.6)
	last_ct_shares = target.readOutput(ORDER)
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



def get_measurements(pico, num_measures, preTrigger, postTrigger):
    pico.runBlock()

    state_used = batchRun()
    data, triggerbuf = pico.receiveData()
    trig_offsets = pico.get_trig_offsets()
    data = np.array(data, dtype=np.int16)
    for i in range(40):
        if not TV: break
        plt.figure(figsize=(8, 4))  # 每次创建新窗口
        plt.plot(data[i], color="#114cd6")
        plt.title(f"Trace {i+1}/{num_traces}")
        plt.xlabel("Sample Points")
        plt.ylabel("Amplitude")
        plt.grid(True)

        plt.show()  # 显示窗口，等待用户关闭后才继续
    shifted = 0
    for i in range(0, num_measures):
    	if (trig_offsets[i]//1000) > 800:
    	    data[i] = np.roll(data[i], 1)
    	    shifted += 1
    print("Shifted: %d"%shifted)
    if args.with_trigger:
        trigger = np.array(triggerbuf, dtype=np.int16)
        for i in range(0, num_measures):
    	    if (trig_offsets[i]//1000) > 800:
    	        trigger[i] = np.roll(trigger[i], 1)

    if args.with_trigger:
        return data, trigger, state_used.astype(np.uint16).ravel() # X
    else:
        return data, None, state_used.astype(np.uint16).ravel() # X


N = 40            # traces per block
M = 1             # number of blocks
plot_delta = 40
if not TV and not args.rngoff:
    N = 5000            # traces per block
    M = 20000             # number of blocks
    plot_delta = 40000
if not TV and args.rngoff:
    N = 5000            # traces per block
    M = 20             # number of blocks
    plot_delta = 10000
preTrigger  = 150 # samples to record BEFORE trigger
if NORMAL_FRE:
    preTrigger = 400
num_traces = 0

nbatch = N
nstate = 2
init_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
init_pt=np.zeros([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)
refreshes=[]
if not args.rngoff:
    flags_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
    # plaintext are all random
    flags_pt=np.ones([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)
    # random key, fixed key is configured in flags_key[0,:]
    if nstate != 1:
        flags_key[1,:] = 1
    for i in range(ORDER):
        for j in range(16):
            refreshes.append([('k',16*i+j),('k',16*ORDER+j)])

if args.rngoff:
    flags_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
    flags_pt=np.zeros([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)
    for i in range(16):
        # the last share of plaintext is random
        flags_pt[:, 10 + i + 16 * ORDER] = 1
    for i in range(16):
        # the last share of key of random set is random
        flags_key[1,i+16*ORDER] = 1


# samples to record AFTER/WHILE trigger
if args.univ_ttest:
    # postTrigger = 6625
    if THREE_STAGED:
        if NORMAL_FRE:
            postTrigger = 16600
        else:
            postTrigger = int(10500/2)+375
    else:
        if NORMAL_FRE:
            postTrigger = 20600
        else:
            postTrigger = int(13000/2)+375
else:
    postTrigger = 6625

"""PicoScope"""
pico = PicoScope(preTrigger, postTrigger, nbatch)
pico.setupDataChannel(ORDER, args)
pico.setupTriggerChannel()#
pico.setupTimeBase()
pico.setupSeqmode(nbatch)
pico.setupBuffer()

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
    data, trigger, X = get_measurements(pico, N, preTrigger, postTrigger)

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
# ps.ps6000CloseUnit(chandle)
pico.close()


