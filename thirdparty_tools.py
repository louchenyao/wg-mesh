#! /usr/bin/env python3

import os
import tempfile


def build_any_proxy(output_path):
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = os.path.join(tmp_dir, "go-any-proxy")
        exe_path = os.path.join(proj_dir, "any_proxy")

        os.system(
            f"cd {tmp_dir} && git clone --depth 1 https://github.com/ryanchapman/go-any-proxy.git")
        os.system(f"cd {proj_dir} && GOOS=linux GOARCH=amd64 ./make.bash")
        os.system(f"cp {exe_path} {output_path}")


def build_freedns_go(output_path):
    with tempfile.TemporaryDirectory() as tmp_dir:
        proj_dir = os.path.join(tmp_dir, "freedns-go")
        exe_path = os.path.join(proj_dir, "freedns-go")

        assert(os.system(
            f"cd {tmp_dir} && git clone --depth 1 https://github.com/tuna/freedns-go.git") == 0)
        assert(
            os.system(f"cd {proj_dir} && GOOS=linux GOARCH=amd64 go build") == 0)
        assert(os.system(f"cp {exe_path} {output_path}") == 0)


def install_wireguard():
    assert(os.system("sudo add-apt-repository -y ppa:wireguard/wireguard") == 0)
    assert(os.system("sudo apt update") == 0)
    assert(os.system("sudo apt install -y wireguard") == 0)


def install_golang():
    assert(os.system("sudo add-apt-repository -y ppa:longsleep/golang-backports") == 0)
    assert(os.system("sudo apt update") == 0)
    assert(os.system("sudo apt install -y golang-go") == 0)


if __name__ == "__main__":
    install_golang()
    install_wireguard()
