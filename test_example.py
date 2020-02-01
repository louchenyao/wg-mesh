import os
import subprocess
import time

import example
from cli import key_dir

def test_gen_net():
    # TODO: we can imporve the test by automatically generating a test environment based on NS
    # just do somke test
    net = example.gen_net(True)

def test_cli():
    # somke test..
    assert(os.system(f"mv {key_dir} bak") == 0)
    assert(os.system(f"mkdir {key_dir}") == 0)
    assert(os.system(f"./example.py genkey all") == 0)
    assert(os.path.exists(os.path.join(key_dir, "iPhone.key")))

    assert(os.system(f"./example.py gen-client-conf iPhone") == 0)

    # Be nice to CI machines. It will cause the CI agent to lose the connection.
    # p = subprocess.Popen(["./example.py", "up", "iPhone"])
    # time.sleep(3)
    # p.terminate()
    # p.wait()
    # assert(p.returncode == 0)

    assert(os.system(f"rm -r {key_dir}") == 0)
    assert(os.system(f"mv bak {key_dir}") == 0)