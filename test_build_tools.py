from build_tools import build_any_proxy, build_freedns_go

import os
import tempfile


def test_build_any_proxy():
    with tempfile.TemporaryDirectory() as tmp_dir:
        build_any_proxy(tmp_dir)
        assert(os.path.isfile(os.path.join(tmp_dir, "any_proxy")))


def test_build_freedns_go():
    with tempfile.TemporaryDirectory() as tmp_dir:
        build_freedns_go(tmp_dir)
        assert(os.path.isfile(os.path.join(tmp_dir, "freedns-go")))
