import pty
import os
import sys

def main():
    def read(fd):
        try:
            data = os.read(fd, 1024)
        except OSError:
            return b""
        with open("pty.log", "ab") as f:
            f.write(data)
        return data

    pty.spawn(os.environ.get("SHELL", "bash"), read)

if __name__ == "__main__":
    main()
