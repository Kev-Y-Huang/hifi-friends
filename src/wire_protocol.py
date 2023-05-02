import struct

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