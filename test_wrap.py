import pty
import os
import sys

def read(fd):
    data = os.read(fd, 1024)
    with open("pty.log", "ab") as f:
        f.write(data)
    return data

pty.spawn(["bash", "-c", "echo Hello; sleep 1; echo World"], read)
