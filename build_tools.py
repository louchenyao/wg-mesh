#! /usr/bin/env python3

import os
import subprocess
import tempfile

def run(cmd, cwd, print_details=True):
    t = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True)
    if print_details:
        print(f"cmd: {cmd}")
        print(f"stdout:\n{t.stdout.decode()}")
        print(f"stderr:\n{t.stderr.decode()}")
        print("")

    assert(t.returncode == 0)
    

def build_any_proxy(output_path):
    with tempfile.TemporaryDirectory() as tmp_dir:
        run("git clone --depth 1 https://github.com/ryanchapman/go-any-proxy.git", tmp_dir)
        run("GOOS=linux GOARCH=amd64 ./make.bash", os.path.join(tmp_dir, "go-any-proxy"))
        run(f"cp ./any_proxy {output_path}", os.path.join(tmp_dir, "go-any-proxy"))

def build_freedns_go(output_path):
    with tempfile.TemporaryDirectory() as tmp_dir:
        run("git clone --depth 1 https://github.com/tuna/freedns-go.git", tmp_dir)
        run("GOOS=linux GOARCH=amd64 go build", os.path.join(tmp_dir, "freedns-go"))
        run(f"cp ./freedns-go {output_path}", os.path.join(tmp_dir, "freedns-go"))
