#! /usr/bin/env python3

import os
import subprocess

def list_ns():
    p = subprocess.run(["ip", "netns"], stdout=subprocess.PIPE)
    return p.stdout.decode().splitlines()

def del_ns(ns):
    # for unknown reasons, the listed name may be "hub (id: 0)"
    ns = ns.split(" ")[0]
    assert(os.system(f"sudo ip netns del {ns}") == 0)

for ns in list_ns():
    print(f"delete {ns}")
    del_ns(ns)
