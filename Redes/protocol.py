import struct
import hashlib

# Header format: sequence (4 bytes), payload_len (4 bytes), md5 (16 bytes)
DATA_HDR_STRUCT = struct.Struct("!II16s") 

CHUNK_SIZE = 1400  

def make_data_packet(seq: int, payload: bytes) -> bytes:
    payload_len = len(payload)
    md5 = hashlib.md5(payload).digest()  # 16 bytes
    header = DATA_HDR_STRUCT.pack(seq, payload_len, md5)
    return header + payload

def parse_data_packet(packet: bytes):
    if len(packet) < DATA_HDR_STRUCT.size:
        raise ValueError("Packet too small for header")
    seq, payload_len, md5 = DATA_HDR_STRUCT.unpack(packet[:DATA_HDR_STRUCT.size])
    payload = packet[DATA_HDR_STRUCT.size:DATA_HDR_STRUCT.size + payload_len]
    return seq, payload_len, md5, payload

def md5_of_bytes(b: bytes) -> bytes:
    return hashlib.md5(b).digest()
