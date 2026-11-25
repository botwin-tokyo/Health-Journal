"""One-job-at-a-time helper. systemd provides the namespace and resource boundary."""

import array
import fcntl
import json
import os
import pwd
import signal
import socket
import struct
import subprocess
import sys
import uuid

from .protocol import MAX_INPUT, MAX_OUTPUT, exact


def expired(signum, frame):
    raise TimeoutError("parser_timeout")


def main():
    allowed_uid = pwd.getpwnam("health03-worker").pw_uid
    path = "/run/health03-parser/api.sock"
    if os.path.exists(path):
        os.unlink(path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(path)
        # Dedicated worker IPC group; parent directory is restricted.
        os.chmod(path, 0o660)  # nosec B103
        listener.listen(1)
        while True:
            peer, _ = listener.accept()
            with peer:
                peer.settimeout(310)
                fd = None
                try:
                    _, uid, _ = struct.unpack(
                        "3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                    )
                    if uid != allowed_uid:
                        continue
                    prefix, ancillary, flags, _ = peer.recvmsg(4, socket.CMSG_SPACE(4))
                    received = array.array("i")
                    for level, kind, value in ancillary:
                        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                            received.frombytes(value[: len(value) - len(value) % received.itemsize])
                    if len(received) != 1 or flags & socket.MSG_CTRUNC:
                        for item in received:
                            os.close(item)
                        raise ValueError("invalid_descriptor")
                    fd = received[0]
                    size = struct.unpack("!I", prefix + exact(peer, 4 - len(prefix)))[0]
                    if size > 4096:
                        raise ValueError("invalid_request")
                    header = json.loads(exact(peer, size))
                    if set(header) != {"operation", "job_id", "length"}:
                        raise ValueError("invalid_request")
                    uuid.UUID(header["job_id"])
                    if type(header["length"]) is not int or not 0 <= header["length"] <= MAX_INPUT:
                        raise ValueError("invalid_length")
                    if fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY:
                        raise ValueError("writable_descriptor")
                    required_seals = (
                        fcntl.F_SEAL_WRITE
                        | fcntl.F_SEAL_GROW
                        | fcntl.F_SEAL_SHRINK
                        | fcntl.F_SEAL_SEAL
                    )
                    if fcntl.fcntl(fd, fcntl.F_GET_SEALS) & required_seals != required_seals:
                        raise ValueError("unsealed_descriptor")
                    with os.fdopen(os.dup(fd), "rb") as stream:
                        payload = stream.read(MAX_INPUT + 1)
                    if len(payload) != header["length"]:
                        raise ValueError("invalid_length")
                    if header["operation"] not in {"parse_pdf", "parse_csv", "render_report"}:
                        raise ValueError("invalid_operation")
                    os.lseek(fd, 0, os.SEEK_SET)
                    child = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "parser_service.runner",
                            header["operation"],
                            str(fd),
                        ],
                        pass_fds=(fd,),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        env={
                            "PATH": "/usr/bin:/bin",
                            "LANG": "C.UTF-8",
                            "PYTHONPATH": "/opt/health03/current/backend",
                            "TMPDIR": "/work",
                        },
                        start_new_session=True,
                    )
                    try:
                        result, _ = child.communicate(timeout=300)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                        raise ValueError("parser_timeout") from None
                    if child.returncode:
                        raise ValueError("parser_rejected_input")
                    if len(result) > MAX_OUTPUT:
                        raise ValueError("output_too_large")
                    peer.sendall(struct.pack("!I", len(result)) + result)
                except Exception:
                    result = b'{"error":"parser_rejected_input"}'
                    try:
                        peer.sendall(struct.pack("!I", len(result)) + result)
                    except OSError:
                        pass
                finally:
                    signal.alarm(0)
                    if fd is not None:
                        os.close(fd)


if __name__ == "__main__":
    main()
