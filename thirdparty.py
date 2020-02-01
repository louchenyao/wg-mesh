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
    assert(os.system("wg --help") == 0)
    # ???
    # assert(os.system("sudo modprobe wireguard"))


def install_golang():
    assert(os.system("sudo add-apt-repository -y ppa:longsleep/golang-backports") == 0)
    assert(os.system("sudo apt update") == 0)
    assert(os.system("sudo apt install -y golang-go") == 0)
    assert(os.system("go version") == 0)


def install_utils():
    assert(os.system("sudo apt update") == 0)
    assert(os.system("sudo apt install -y ipset traceroute") == 0)


def conf_sysctl():
    # https://www.cyberciti.biz/cloud-computing/increase-your-linux-server-internet-speed-with-tcp-bbr-congestion-control/
    with tempfile.TemporaryDirectory() as tmp_dir:
        conf_path = os.path.join(tmp_dir, "999-custom-net.conf")
        with open(conf_path, "w") as f:
            f.write("net.core.default_qdisc=fq\n")
            f.write("net.ipv4.tcp_congestion_control=bbr\n")
            f.write("net.ipv4.ip_forward = 1\n")
            f.write("net.ipv4.conf.all.rp_filter = 0\n")
            f.write("net.ipv4.conf.default.rp_filter = 0\n")
        assert(os.system(f"sudo cp {conf_path} /etc/sysctl.d") == 0)
    assert(os.system(f"sudo sysctl --system") == 0)


if __name__ == "__main__":
    install_utils()
    install_golang()
    install_wireguard()
    conf_sysctl()


    bin_dir = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "bin"
    )
    os.system(f"mkdir -p {bin_dir}")
    build_freedns_go(bin_dir)
    build_any_proxy(bin_dir)
    