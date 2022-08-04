# This file contains classes for ZMQ socket communication with gnuradio flowgraphs

import zmq
import pmt
import array

# the following tcp addresses will be used by default unless overridden
TCP_TX = "tcp://127.0.0.1:5555"  # for sending data to transmitter
TCP_RX = "tcp://127.0.0.1:5556"  # for getting data from receiver


# this class creates a pull socket for grabbing messages
# from a flowgraph
class ZmqPullMsgSocket:
    def __init__(self, tcp_str=TCP_RX, do_acs = False):
        self.context = zmq.Context()
        self.receiver = self.context.socket(zmq.PULL)
        self.receiver.connect(tcp_str)
        self.do_acs = do_acs

    def poll_bytes(self, verbose=False):
        raw_msg = self.receiver.recv()
        byte_list = pdu_to_payload_bytes(raw_msg)
        if self.do_acs:
            if (sum(byte_list[:-1]) % 256) == byte_list[-1]:
                return byte_list[:-1]
            else:
                if verbose:
                    print("Warning: Checksum did not match")
                return []
        else:
            return byte_list

    def poll_str(self, verbose=False):
        byte_list = self.poll_bytes(verbose=verbose)
        return bytes_to_string(byte_list)

    def close(self):
        if not self.receiver.closed:
            self.receiver.setsockopt(zmq.LINGER, 0)
            self.receiver.close()
        if not self.context.closed:
            self.context.destroy(0)


# This function takes a raw message and extracts the payload as bytes
def pdu_to_payload_bytes(raw_msg):
    pdu_rx = pmt.deserialize_str(raw_msg)
    payload_pmt = pmt.cdr(pdu_rx)
    payload = list(pmt.u8vector_elements(payload_pmt))
    return payload


def bytes_to_string(byte_list):
    char_list = list(map(chr, byte_list))
    return "".join(char_list)


# this class creates a push socket for sending messages
# to a flowgraph as well as the methods required to send
# both byte and string data
class ZmqPushMsgSocket:
    def __init__(self, tcp_str=TCP_TX, do_acs=False, do_header=False):
        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.bind(tcp_str)
        self.do_acs = do_acs
        self.do_header = do_header  # for gnuradio CAC-TS block

    # sends raw bytes via ZMQ connection; this fn assumes that
    # the ZMQ source on the other side is expecting packed bytes
    # of type unsigned char
    def send_raw_bytes(self, byte_list):

        # get payload size
        payload_size = len(byte_list)
        # build an empty vector
        data = pmt.make_u8vector(payload_size, 0x00)
        # fill the vector with unsigned byte data to send
        for i in range(payload_size):
            pmt.u8vector_set(data, i, byte_list[i])
        # build the message, which is a pair consisting of
        # the message metadata (not needed here) and the
        # information we want to send (the vector)
        msg = pmt.cons(pmt.PMT_NIL, data)
        # the message must be serialized as a string so that
        # it's in the form the gnuradio source expects
        msg = pmt.serialize_str(msg)
        self.socket.send(msg)

    # Sends a message framed in the basic gnuradio format:
    #   - preamble
    #   - two bytes containing the payload length (MSB)
    #   - a second copy of the length byte pair
    #   - the payload
    #
    # Both the preamble and the byte_list must be lists of packed,
    # 8-bit values.
    def send_framed_bytes(self, preamble, byte_list):

        # get payload size
        payload_size = len(byte_list)

        # build the framed vector (starting/ending with some dead air)
        framed_list = 10 * [0x00] + preamble
        # this is the header format GNU Radio expects
        if self.do_header:
            framed_list.append(0x00)
            framed_list.append(payload_size)
            framed_list.append(0x00)
            framed_list.append(payload_size)
        framed_list += byte_list
        if self.do_acs:
            payload_sum = sum(byte_list)
            framed_list.append(payload_sum % 256)
        framed_list += 10 * [0x00]

        # send it
        self.send_raw_bytes(framed_list)

    # converts the string to a byte list and sends it via
    # the preceding functions
    def send_framed_str(self, preamble, in_str):
        byte_list = in_str.encode('utf-8')
        self.send_framed_bytes(preamble=preamble,
                               byte_list=byte_list)

    def close(self):
        if not self.socket.closed:
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.close()
        if not self.context.closed:
            self.context.destroy(0)
