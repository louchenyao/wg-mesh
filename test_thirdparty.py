from thirdparty import build_any_proxy, build_freedns_go, install_wireguard, install_golang, conf_sysctl

import os
import subprocess
import tempfile


def test_build_any_proxy():
    install_golang()
    with tempfile.TemporaryDirectory() as tmp_dir:
        build_any_proxy(tmp_dir)
        assert(os.path.isfile(os.path.join(tmp_dir, "any_proxy")))


def test_build_freedns_go():
    install_golang()
    with tempfile.TemporaryDirectory() as tmp_dir:
        build_freedns_go(tmp_dir)
        assert(os.path.isfile(os.path.join(tmp_dir, "freedns-go")))


def test_install_golang():
    install_golang()
    assert(os.system("sudo go version") == 0)


def test_install_wireguard():
    install_wireguard()
    assert(os.system("sudo wg") == 0)


def test_conf_sysctl():
    conf_sysctl()
    qdisc = subprocess.check_output(
        ["sysctl", "net.core.default_qdisc"]).decode().strip()
    cc = subprocess.check_output(
        ["sysctl", "net.ipv4.tcp_congestion_control"]).decode().strip()
    forward = subprocess.check_output(
        ["sysctl", "net.ipv4.ip_forward"]).decode().strip()
    assert(qdisc == "net.core.default_qdisc = fq")
    assert(cc == "net.ipv4.tcp_congestion_control = bbr")
    assert(forward== "net.ipv4.ip_forward = 1" )
