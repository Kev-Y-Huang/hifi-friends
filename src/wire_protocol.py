import struct, os

# Packet format:
# - 4 byte unsigned integer for data length (N)
# - 1 byte unsigned integer for operation code
# - N bytes for packet data


def pack_packet(server_id: int, gen_number: int, operation: int, input: str) -> bytes:
    msg = f'{server_id}|{gen_number}|{operation}|{input}'.encode()
    return msg
    # encoded_name = bytes(server_id, 'utf-8')    # Or other appropriate encoding
    # name_len = len(encoded_name)
    # encoded_input = input.encode('utf-8')
    # return struct.pack(f"!I{name_len}sIB",
    #                    name_len,
    #                    encoded_name,
    #                    len(encoded_input),
    #                    operation) + encoded_input


def unpack_packet(packet: bytes) -> tuple:
    decoded = packet.decode().split('|')
    return decoded[0], decoded[1], decoded[2], decoded[3]
    # name_len = struct.unpack("!I", packet[:4])[0]
    # username = packet[4:4 + name_len].decode('utf-8')
    #
    # data_len, operation = struct.unpack("!IB", packet[4 + name_len:9 + name_len])
    # data = packet[9 + name_len:9 + name_len + data_len]
    # output = data.decode('utf-8')
    # return username if username else "", operation, output


def pack_opcode(opcode: int) -> bytes:
    return struct.pack("!B", opcode)


def unpack_opcode(opcode: bytes) -> int:
    return struct.unpack("!B", opcode)[0]

# Encodes filename size as 16 bit binary, limit your filename length to 255 bytes
def pack_file_name_size(file_name: str) -> bytes:
    size = bin(len(file_name))[2:].zfill(16)
    return size.encode()

# Encode filesize as 32 bit binary
def pack_file_size(file_size: str) -> bytes:
    file_size = bin(file_size)[2:].zfill(32)
    return file_size.encode()

def unpack_size(size: bytes) -> str:
    return int(size.decode(), 2)