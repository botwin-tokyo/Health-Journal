import array
import fcntl
import json
import os
import socket
import struct

MAX_INPUT = 25 * 1024 * 1024
MAX_OUTPUT = 25 * 1024 * 1024


def exact(sock, length):
    parts = bytearray()
    while len(parts) < length:
        chunk = sock.recv(min(65536, length - len(parts)))
        if not chunk:
            raise ValueError("Incomplete helper message")
        parts.extend(chunk)
    return bytes(parts)


def invoke(operation, payload, job_id):
    if len(payload) > MAX_INPUT or operation not in {"parse_pdf", "parse_csv", "render_report"}:
        raise ValueError("Invalid parser request")
    fd = os.memfd_create("health03-job", os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC)
    readonly = None
    try:
        with os.fdopen(os.dup(fd), "wb") as output:
            output.write(payload)
        fcntl.fcntl(
            fd,
            fcntl.F_ADD_SEALS,
            fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL,
        )
        readonly = os.open(f"/proc/self/fd/{fd}", os.O_RDONLY)
        header = json.dumps(
            {"operation": operation, "job_id": str(job_id), "length": len(payload)}
        ).encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
            peer.settimeout(315)
            peer.connect("/run/health03-parser/api.sock")
            peer.sendmsg(
                [struct.pack("!I", len(header)) + header],
                [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [readonly]))],
            )
            size = struct.unpack("!I", exact(peer, 4))[0]
            if size > MAX_OUTPUT:
                raise ValueError("Helper output too large")
            return exact(peer, size)
    finally:
        os.close(fd)
        if readonly is not None:
            os.close(readonly)
