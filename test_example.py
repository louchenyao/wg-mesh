import os
import subprocess
import time

import example
from cli import key_dir
from mesh import NS

def test_gen_net_smoke():
    net = example.gen_net(True, mock_net = False)

def test_gen_net_mock():
    net = example.gen_net(True, mock_net = True)
    net.up_mock_net()
    for h in net.hosts:
        print(f"Starting {h}")
        net.up(h)
    
    assert(os.system(NS("iPhone").gen_cmd("ping 10.56.1.1 -c 1")) == 0)
    assert(os.system(NS("iPhone").gen_cmd("ping 10.56.1.2 -c 1")) == 0)
    assert(os.system(NS("iPhone").gen_cmd("ping 10.56.200.21 -c 1")) == 0)
    if os.environ.get("CI") == None:
        assert(os.system(NS("iPhone").gen_cmd("host google.com 10.56.1.1")) == 0)
    # todo: test traceroute

    for h in net.hosts:
        net.down(h)
    net.down_mock_net()

def test_cli():
    assert(os.system(f"mv {key_dir} bak") == 0)
    assert(os.system(f"mkdir {key_dir}") == 0)
    assert(os.system(f"./example.py genkey all") == 0)
    assert(os.path.exists(os.path.join(key_dir, "iPhone.key")))
    assert(os.system(f"./example.py gen-client-conf iPhone") == 0)

    # TODO: get this test works
    # p = subprocess.Popen(["./example.py", "mock"], stdout=subprocess.PIPE)
    # while p.poll() == None:
    #     out = p.stdout.read().decode()
    #     print(out, end="", flush=True)
    #     if "is up" in out:
    #         p.terminate()
    #         p.wait()
    #         break
    # assert(p.returncode == 0)

    assert(os.system(f"rm -r {key_dir}") == 0)
    assert(os.system(f"mv bak {key_dir}") == 0)