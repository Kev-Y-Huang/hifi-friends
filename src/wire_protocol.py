import struct

# Packet format:
# - 4 byte unsigned integer for data length (N)
# - 1 byte unsigned integer for operation code
# - N bytes for packet data


def pack_packet(username: str, operation: int, input: str) -> bytes:
    encoded_name = bytes(username, 'utf-8')    # Or other appropriate encoding
    name_len = len(encoded_name)
    encoded_input = input.encode('utf-8')
    return struct.pack(f"!I{name_len}sIB",
                       name_len,
                       encoded_name,
                       len(encoded_input),
                       operation) + encoded_input


def unpack_packet(packet: bytes) -> tuple:
    name_len = struct.unpack("!I", packet[:4])[0]
    username = packet[4:4 + name_len].decode('utf-8')

    data_len, operation = struct.unpack("!IB", packet[4 + name_len:9 + name_len])
    data = packet[9 + name_len:9 + name_len + data_len]
    output = data.decode('utf-8')
    return username if username else "", operation, output