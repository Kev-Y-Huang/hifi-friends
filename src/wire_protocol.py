import struct

from utils import Operation, ServerOperation, Update, Message


def pack_packet(server_id: int, gen_number: int, input: str) -> bytes:
    msg = f'{server_id}|{gen_number}|{input}'.encode()
    return msg


def unpack_packet(packet: bytes) -> tuple:
    decoded = packet.decode().split('|')
    return int(decoded[0]), int(decoded[1]), decoded[2]


def pack_server_opcode(server_opcode: ServerOperation) -> bytes:
    return struct.pack("!B", server_opcode.value)


def unpack_server_opcode(data: bytes) -> ServerOperation:
    output = struct.unpack("!B", data)[0]
    return ServerOperation(output)

def pack_opcode(opcode: Operation) -> bytes:
    return struct.pack("!B", opcode.value)


def unpack_opcode(data: bytes) -> Operation:
    output = struct.unpack("!B", data)[0]
    return Operation(output)

def pack_msgcode(msgcode: Message) -> bytes:
    return struct.pack("!B", msgcode.value)

def unpack_msgcode(data: bytes) -> Message:
    output = struct.unpack("!B", data)[0]
    return Message(output)


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


def pack_state(song_index: int, frame_index: int, action: Update) -> bytes:
    return struct.pack("!III", song_index, frame_index, action.value)


def unpack_state(data: bytes) -> tuple:
    song_index, frame_index, action = struct.unpack("!III", data)
    return song_index, frame_index, Update(action)


def pack_audio_meta(width: int, sample_rate: int, channels: int) -> bytes:
    return struct.pack("!BIII", 0, width, sample_rate, channels)


def unpack_audio_meta(data: bytes) -> tuple:
    return struct.unpack("!BIII", data)
