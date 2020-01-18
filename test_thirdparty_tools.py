from thirdparty_tools import build_any_proxy, build_freedns_go, install_wireguard, install_golang

import os
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
