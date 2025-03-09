from chipwhisperer.capture.targets.CW305 import CW305
import matplotlib.pyplot as plt
import chipwhisperer as cw
from tqdm import tqdm
from Cryptodome.Cipher import AES
import numpy as np
import time

import re

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

def parse_arguments():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--order', metavar='order', required=False, default=2,
                            help='program the firmware according to the order', type=int)
    parser.add_argument('--initial_sharing', metavar='initial_sharing', required=False, default=2,
                            help='0: key and plaintext are set to all zeros, for debugging; 1: key and plaintext without initial sharing, for rngoff option; 2: both key and plaintext with initial sharing, it is the regular case.', type=int)
    parser.add_argument('--design', metavar='design', required=False, default='noia41',
                            help='possible values: noia41, noia51, pini41, pini51', type=str)
    parser.add_argument('--rngoff', action="store_true",
                            help='choose the bitsteam file with rng on')
    parser.add_argument('--print_dpay', action="store_true",
                            help='print the dpay array to copy to the usb.c')
    args = parser.parse_args()
    return args


args = parse_arguments()

ORDER = args.order
DOM=True
bslocation=""
if args.rngoff:
    bslocation = args.design + "/" + "rngoff"
else:
    bslocation = args.design + "/" + "rngon"

if DOM:
    bitstream_path = "./bitstream/%s/cw305_top_o%d.bit" % ( bslocation, ORDER)
else:
    bitstream_path = "E:/2025/SMAesH-challenge/fpga_designs/SMAesH/cw305_ucg_target/cw305_ucg_target.runs/impl_1/cw305_top_trig_wrng_o%d.bit" % ORDER

print("####################")
print("# Programming the target with default bitsteam")
print("####################\n")
print(bitstream_path)
target = CW305()
target.con(bsfile=bitstream_path, force=True)

FpgaClkFreq=10.0E6 #1.5625E6#
target.pll.pll_outfreq_set(FpgaClkFreq, 1)
target.pll.pll_outfreq_set(10e6, 0)

target.clkusbautooff = True
target.clksleeptime = 1

print("####################")
print("# Functional testing")
print("####################")

nbatch = 5000
nstate = 2
if args.initial_sharing == 0:
    nstate = 1
init_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
init_pt=np.zeros([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)

if args.initial_sharing == 0:
    # key and pt are fixed zeros, and no refresh
    flags_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
    flags_pt=np.zeros([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)

if args.initial_sharing == 1 or args.initial_sharing == 2:
    flags_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
    flags_pt=np.zeros([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)
    for i in range(16):
        # set random plaintext
        flags_pt[1:, 10 + i + 16 * ORDER] = 1

refreshes=[]
if args.initial_sharing == 2:
    # provides key and plaintext with initial sharing
    for i in range(ORDER):
        for j in range(16):
            refreshes.append([('k',16*i+j),('k',16*ORDER+j)])
            refreshes.append([('t',16*i+j),('t',16*ORDER+j)])

# if args.initial_sharing == 2:
#     flags_key=np.zeros([nstate, 16*(ORDER + 1)],dtype=np.uint8)
#     flags_pt=np.zeros([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)
#     for i in range(16):
#         # set random plaintext
#         flags_pt[:, 10 + i + 16 * ORDER] = 1



# # plaintext are all random
# if args.initial_sharing == 2:
#     flags_pt=np.ones([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)
# else:
#     flags_pt=np.zeros([nstate, 10 + 16*(ORDER + 1)],dtype=np.uint8)

# # When args.initial_sharing == 1, there's no intial sharing
# if args.initial_sharing == 1:
#     for i in range(16):
#         # the last share of plaintext is random
#         flags_pt[:, 10 + i + 16 * ORDER] = 1
#     for i in range(16):
#         # the last share of key of random set is random
#         flags_key[1,i+16*ORDER] = 1


# # random key, fixed key is configured in flags_key[0,:]
# if args.initial_sharing == 2:
#     flags_key[1,:] = 1
#     # initial_sharing for key in fixed set.
#     for i in range(ORDER):
#         if args.initial_sharing != 2: break
#         for j in range(16):
#             refreshes.append([('k',16*i+j),('k',16*ORDER+j)])
        #     print(('k',16*i+j),('k',16*ORDER+j))
        # print()
seed=0xd8fdc297
seed=None
gen_settings=args.print_dpay
key_used,pt_used,state_used = target.batchRun(nbatch, nstate, init_key, init_pt, flags_key, flags_pt, refreshes, gen_settings=gen_settings, seed=seed)#
## order 1: 3.4, order 2: 5.6
if ORDER == 1:
    # 4.18 do not work
    time.sleep(4.19)
if ORDER == 2:
    time.sleep(6.58)

last_ct_shares = target.readOutput(ORDER)
last_ct_shares = bytes(last_ct_shares)
last_ct = xorbytes(last_ct_shares, ORDER)
printBytes("last_ct_shares = ", bytes(reversed(last_ct_shares)))
printBytes("last_ct = ", last_ct)
printBytes("last_key_used = ", bytes(reversed(key_used[-1])))
printBytes("last_pt_used = ", bytes(reversed(pt_used[-1])))


sh_key = bytes(key_used[-1])
sh_plaintext = bytes(pt_used[-1,10:])
umsk_key = get_umsk_data(sh_key, ORDER)
cipher = AES.new(umsk_key, AES.MODE_ECB)
umsk_plaintext = get_umsk_data(sh_plaintext, ORDER)
umsk_ciphertext = cipher.encrypt(umsk_plaintext)

sh_ciphertext = bytes(last_ct_shares)
hw_ciphertext = get_umsk_data(sh_ciphertext, ORDER)

printBytes("ciphertext from hardware: ", hw_ciphertext)
printBytes("ciphertext from local:    ", umsk_ciphertext)
# printBytes("ciphertext from local:    ", bytes(reversed(umsk_ciphertext)))
printBytes("plaintext from local:    ", umsk_plaintext)
printBytes("key from local:    ", umsk_key)

assert (hw_ciphertext == umsk_ciphertext)
