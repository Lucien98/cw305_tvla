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
    data_big = bytes(reversed(data_little))
    return data_big

# Functional testing
NTEST = 100
MBATCHSIZE = 2048

# Benchmark settings
TESTED_BATCHSIZE = 2**np.arange(1,11) 

bitstream_path = "E:/2025/SMAesH-challenge/fpga_designs/SMAesH/cw305_ucg_target/cw305_ucg_target.runs/impl_1/cw305_top.bit"

print("####################")
print("# Programming the target with default bitsteam")
print("####################\n")
print(bitstream_path)
target = CW305()
target.con(bsfile=bitstream_path, force=False)

target.clkusbautooff = True
target.clksleeptime = 1

print("####################")
print("# Functional testing")
print("####################")

# for i in tqdm(range(NTEST),desc="Functional testing random pt and random key"):
#     batchsize = np.random.randint(1,MBATCHSIZE)

#     # Do the batch_run
#     keys,pts = target.batchRun(batchsize=batchsize,random_key=True,
#         random_pt=True)
    
#     key = bytes(keys[-1])
#     pt = bytes(pts[-1])
#     last_ct = target.readOutput()

#     # Verify the last cipher text
#     cipher = AES.new(key, AES.MODE_ECB)
#     ref = cipher.encrypt(pt)

#     if ref != bytes(last_ct):
#         print("Test Failed")
#         exit(-1)

ORDER = 1



# def main():
nbatch = 1
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
for i in range(ORDER):
    if nstate == 1: break
    for j in range(16):
        refreshes.append([('k',16*i+j),('k',16*ORDER+j)])
#         print(('k',16*i+j),('k',16*ORDER+j))
#     print()
# print(refreshes)
# print(init_pt)
# print(init_key)
# print(flags_key)
# print(flags_pt)

key_used,pt_used,state_used = target.batchRun(nbatch, nstate, init_key, init_pt, flags_key, flags_pt, refreshes)

last_ct_shares = target.readOutput()
last_ct_shares = bytes(last_ct_shares)
last_ct = xorbytes(last_ct_shares, 1)
printBytes("last_ct_shares = ", last_ct_shares)
printBytes("last_ct = ", last_ct)
printBytes("last_key_used = ", bytes(key_used[-1]))
printBytes("last_pt_used = ", bytes(pt_used[-1]))


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
printBytes("plaintext from local:    ", umsk_plaintext)
printBytes("key from local:    ", umsk_key)


# if __name__ == '__main__':
#     main()




# for i in tqdm(range(NTEST),desc="Functional testing random pt and fixed key"):
#     batchsize = np.random.randint(1,MBATCHSIZE)

#     key = np.random.randint(0,256,16,dtype=np.uint8).tobytes()
#     target.loadEncryptionKey(key)

#     # Do the batch_run
#     keys,pts = target.batchRun(batchsize=batchsize,random_key=False,
#         random_pt=True)
    
#     pt = bytes(pts[-1])
#     last_ct = target.readOutput()

#     # Verify the last cipher text
#     cipher = AES.new(key, AES.MODE_ECB)
#     ref = cipher.encrypt(pt)

#     if ref != bytes(last_ct):
#         print("Test Failed")
#         exit(-1)

# for i in tqdm(range(NTEST),desc="Functional testing fixed pt and random key"):
#     batchsize = np.random.randint(1,MBATCHSIZE)

#     pt = np.random.randint(0,256,16,dtype=np.uint8).tobytes()
#     target.loadInput(pt)

#     # Do the batch_run
#     keys,pts = target.batchRun(batchsize=batchsize,random_key=True,
#         random_pt=False)
    
#     key = bytes(keys[-1])
#     last_ct = target.readOutput()

#     # Verify the last cipher text
#     cipher = AES.new(key, AES.MODE_ECB)
#     ref = cipher.encrypt(pt)

#     if ref != bytes(last_ct):
#         print("Test Failed")
#         exit(-1)

# for i in tqdm(range(NTEST),desc="Functional testing fixed pt and fixed key"):
#     batchsize = np.random.randint(1,MBATCHSIZE)

#     pt = np.random.randint(0,256,16,dtype=np.uint8).tobytes()
#     target.loadInput(pt)
#     key = np.random.randint(0,256,16,dtype=np.uint8).tobytes()
#     target.loadEncryptionKey(key)

#     # Do the batch_run
#     keys,pts = target.batchRun(batchsize=batchsize,random_key=False,
#         random_pt=False)
    
#     last_ct = target.readOutput()

#     # Verify the last cipher text
#     cipher = AES.new(key, AES.MODE_ECB)
#     ref = cipher.encrypt(pt)

#     if ref != bytes(last_ct):
#         print("Test Failed")
#         exit(-1)

# print("####################")
# print("# Benchmark")
# print("####################")
# tp_all = []
# labels = []
# labels_default = []
# for random_pt in [False,True]:
#     for random_key in [False,True]:
#         tp = []
#         for batchsize in TESTED_BATCHSIZE:
#             print("Running benchmark on batchsize of ",batchsize)
#             start = time.time()
#             for _ in range(NTEST):
#                 target.batchRun(batchsize,random_key,random_pt)
#             end = time.time()
#             tp.append(NTEST*batchsize/(end-start))

#         k = np.random.randint(0,256,dtype=np.uint8).tobytes()
#         p = np.random.randint(0,256,dtype=np.uint8).tobytes()
#         start = time.time()
#         for _ in range(NTEST):
#             if random_key:
#                 target.loadEncryptionKey(k)
#             if random_pt:
#                 target.loadInput(p)
#             target.go()
#         end = time.time()
#         de = NTEST/(end-start)
#         labels.append("rand. pt "+str(random_pt)+" rand. key "+str(random_key))
#         tp_all.append((tp,de))


# plt.figure()
# colors = ["r","g","b","m"]
# plt.subplot(211)
# for i,(label,tp) in enumerate(zip(labels,tp_all)):
#     plt.loglog(TESTED_BATCHSIZE,tp[0],label=label,basex=2,basey=10,color=colors[i])
# plt.ylabel("Enc/sec with batchRun")
# plt.legend()
# plt.grid(True,which="both",ls="--")

# plt.subplot(212)
# for i,(label,tp) in enumerate(zip(labels,tp_all)):
#     plt.loglog(TESTED_BATCHSIZE,np.zeros(len(TESTED_BATCHSIZE)),basex=2,basey=10,color=colors[i])
#     plt.axhline(tp[1],color=colors[i],label=label)
# plt.ylabel("Enc/sec with loadKey")
# plt.xlabel("Batch size")
# plt.legend()
# plt.grid(True,which="both",ls="--")
# plt.show()
