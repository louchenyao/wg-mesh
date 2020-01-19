from ww import Key, NS, Veth, gen_wg, global_ns, IPTableRule, Route, IPSet, chinaip_list, privateip_list, RouteRule

import os
import subprocess
import tempfile


def test_Key():
    with tempfile.TemporaryDirectory() as tmp_dir:
        p = os.path.join(tmp_dir, "tmp.key")

        # new the key
        k = Key(None)
        pk = k.pk
        sk = k.sk
        k.dump(p)
        del k

        # reload teh ky
        k1 = Key(p)
        assert(k1.pk == pk)
        assert(k1.sk == sk)


def test_veth():
    left_ns = NS("left")
    right_ns = NS("right")
    veth = Veth("veth", "10.1.1.1/24", "10.1.1.2/24", left_ns, right_ns)

    left_ns.up()
    right_ns.up()
    veth.up()

    assert(os.system(left_ns.gen_cmd("ping 10.1.1.2 -c 2")) == 0)

    veth.down()
    right_ns.down()
    left_ns.down()


def test_wg():
    left_key = Key(None)
    right_key = Key(None)
    left_ns = NS("left")
    right_ns = NS("right")
    veth = Veth("veth", "10.1.1.1/24", "10.1.1.2/24", left_ns, right_ns)
    left_wg, right_wg = gen_wg("wg0", left_key, right_key, right_wan_ip="10.1.1.2",
                               link_cidr="192.168.1.8/30", port="1234", mtu=1420, left_ns=left_ns, right_ns=right_ns)

    left_ns.up()
    right_ns.up()
    veth.up()
    left_wg.up()
    right_wg.up()

    assert(os.system(left_ns.gen_cmd("ping 192.168.1.10 -c 1")) == 0)
    assert(os.system(left_ns.gen_cmd("ping 192.168.1.10 -c 2")) == 0)

    right_wg.down()
    left_wg.down()
    veth.down()
    right_ns.down()
    left_ns.down()


def test_IPTableRule():
    ns = NS("ns")
    veth = Veth("veth", "10.1.1.1/24", "10.1.1.2/24", global_ns, ns)
    route = Route("1.1.1.1", "10.1.1.1", "main", ns)
    rule = IPTableRule("nat", "POSTROUTING",
                       "-s 10.1.1.2 -j MASQUERADE", global_ns)

    ns.up()
    veth.up()
    route.up()
    rule.up()

    assert(os.system(ns.gen_cmd("ping 1.1.1.1 -c 2")) == 0)

    rule.down()
    route.down()
    veth.down()
    ns.down()

def test_IPSet():
    def is_in_ipset(ipset_name, ip):
        return os.system(f"sudo ipset test {ipset_name} {ip}") == 0

    s1 = IPSet("private_ip", privateip_list(), global_ns)
    s1.up()
    assert(is_in_ipset(s1.name, "10.1.1.1"))
    s1.down()
    
    cip = IPSet("china_ip", chinaip_list(), global_ns)
    cip.up()
    assert(is_in_ipset(cip.name, "114.114.114.114"))
    assert(is_in_ipset(cip.name, "8.8.8.8") == False)
    cip.down()

def test_RouteRule():
    # TODO: RouteRule should work now. But it is a little hard to test.
    pass