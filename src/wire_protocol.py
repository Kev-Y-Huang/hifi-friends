import struct

from utils import ActionType, Operation

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


def pack_opcode(opcode: Operation) -> bytes:
    return struct.pack("!B", opcode.value)


def unpack_opcode(data: bytes) -> Operation:
    output = struct.unpack("!B", data)[0]
    return Operation(output)


def pack_num(num: int, len: int) -> bytes:
    """
    Encodes num as a len bit binary
    """
    return (bin(num)[2:].zfill(len)).encode()


def unpack_num(num: bytes) -> str:
    """
    Decodes num from a len bit binary
    """
    return int(num.decode(), 2)


def pack_state(song_index: int, frame_index: int, action: ActionType) -> bytes:
    return struct.pack("!III", song_index, frame_index, action.value)


def unpack_state(data: bytes) -> tuple:
    song_index, frame_index, action = struct.unpack("!III", data)
    return song_index, frame_index, ActionType(action)


def pack_audio_meta(width: int, sample_rate: int, channels: int) -> bytes:
    return struct.pack("!BIII", 0, width, sample_rate, channels)


def unpack_audio_meta(data: bytes) -> tuple:
    return struct.unpack("!BIII", data)