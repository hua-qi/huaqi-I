import json
import os

path = os.path.expanduser("~/.codeflicker/data.json")
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        for proj, info in list(data.get("projects", {}).items())[:2]:
            print(proj)
            print("History:", info.get("history")[:2])
except Exception as e:
    print(e)
