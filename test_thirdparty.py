from thirdparty import build_any_proxy, build_freedns_go, install_wireguard, install_golang, conf_sysctl

import os
import subprocess
import tempfile


def test_build_any_proxy():
    with tempfile.TemporaryDirectory() as tmp_dir:
        build_any_proxy(tmp_dir)
        assert(os.path.isfile(os.path.join(tmp_dir, "any_proxy")))


def test_build_freedns_go():
    with tempfile.TemporaryDirectory() as tmp_dir:
        build_freedns_go(tmp_dir)
        assert(os.path.isfile(os.path.join(tmp_dir, "freedns-go")))


def test_conf_sysctl():
    conf_sysctl()
    def check(conf_name, expected):
        out = subprocess.check_output(["sysctl", conf_name]).decode().strip()
        value = out.split("=")[1].strip()
        assert(value == expected)

    check("net.core.default_qdisc", "fq")
    check("net.ipv4.tcp_congestion_control", "bbr")
    check("net.ipv4.ip_forward", "1")
    check("net.ipv4.conf.all.rp_filter", "0")
    check("net.ipv4.conf.default.rp_filter", "0")