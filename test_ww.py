from ww import *

import os
import pytest
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

    assert(os.system(left_ns.gen_cmd("timeout 0.2 ping 10.1.1.2 -c 1")) == 0)

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
    net = ConfSet()
    ns = NS("ns")
    net.add(ns)
    net.add(Veth("veth", "10.1.1.1/24", "10.1.1.2/24", global_ns, ns))

    rule = IPTableRule("filter", "OUTPUT", "-d 10.1.1.1 -j DROP", ns)
    
    net.up()

    assert(os.system(ns.gen_cmd("timeout 0.2 ping 10.1.1.1 -c 1")) == 0)
    rule.up()
    assert(os.system(ns.gen_cmd("timeout 0.2 ping 10.1.1.1 -c 1")) != 0)
    rule.down()

    net.down()


def test_IPSet():
    def is_in_ipset(ipset_name, ip):
        return os.system(f"sudo ipset test {ipset_name} {ip}") == 0

    s1 = IPSet("private_ip", privateip_list(), global_ns)
    s1.up()
    assert(is_in_ipset(s1.name, "10.1.1.1"))
    s1.down()

    cip = IPSet("china_ip", chinaip_list(), global_ns)
    cip.up()
    assert(is_in_ipset(cip.name, "114.114.114.114") == True)
    assert(is_in_ipset(cip.name, "8.8.8.8") == False)
    cip.down()


def test_IPSetBundle():
    a = IPSet("a", ["192.168.1.0/24"], global_ns)
    b = IPSet("b", ["192.168.2.0/24"], global_ns)
    c = IPSet("c", ["192.168.3.0/24"], global_ns)
    
    bundle = IPSetBundle(match=[a, b], not_match=[c])
    assert(bundle.gen_iptables_condition() == "-m set --match-set a dst -m set --match-set b dst -m set ! --match-set c dst")


def test_RouteRule():
    net = ConfSet()
    a = NS("a")
    b = NS("b")
    net.add(a)
    net.add(b)
    net.add([
        Veth("ab1", "192.168.1.1/24", "192.168.1.2/24", a, b),
        Veth("ab2", "192.168.10.1/24", "192.168.10.2/24", a, b),
        Route("192.168.1.2", "192.168.10.2", "1", a),
        IPTableRule("filter", "INPUT", "-i ab1-right -j DROP", b),
    ])

    a_iptable = IPTableRule(
        "mangle", "OUTPUT", "-d 192.168.0.0/16 -j MARK --set-mark 1", a)
    a_rule = RouteRule("1", "1", a)

    net.up()

    assert(os.system(a.gen_cmd("timeout 0.2 ping 192.168.1.2 -c 1")) != 0)
    a_iptable.up()
    a_rule.up()
    assert(os.system(a.gen_cmd("timeout 0.2 ping 192.168.1.2 -c 1")) == 0)

    a_iptable.down()
    a_rule.down()
    net.down()


def test_ConfSet():
    net = ConfSet()
    ns = NS("ns")
    net.add(ns)
    net.add(Route("1.1.1.1", "192.168.1.1", "main", ns)) # error: no gateway 192.168.1.1

    with pytest.raises(Exception) as e:
        net.up()
    print(e)
    # ns should be deleted by net due to the exception
    assert(os.system(global_ns.gen_cmd("ip netns exec ns ip addr")) != 0)


def test_Network():
    testbed = ConfSet()
    a_ns = NS("a")
    b_ns = NS("b")
    c_ns = NS("c")
    d_ns = NS("d")
    hub = NS("hub")
    testbed.add([a_ns, b_ns, c_ns, d_ns, hub])
    testbed.add([
        Veth("atohub", "192.168.1.2/24", "192.168.1.1/24", a_ns, hub),
        Veth("btohub", "192.168.2.2/24", "192.168.2.1/24", b_ns, hub),
        Veth("ctohub", "192.168.3.2/24", "192.168.3.1/24", c_ns, hub),
        Veth("dtohub", "192.168.4.2/24", "192.168.4.1/24", d_ns, hub),
        Route("default", "192.168.1.1", "main", a_ns),
        Route("default", "192.168.2.1", "main", b_ns),
        Route("default", "192.168.3.1", "main", c_ns),
        Route("default", "192.168.4.1", "main", d_ns),
    ])

    net = Network()
    a = Host("a", "192.168.1.2", Key(None), a_ns)
    b = Host("b", "192.168.2.2", Key(None), b_ns)
    c = Host("c", "192.168.3.2", Key(None), c_ns)
    d = Host("d", "192.168.4.2", Key(None), d_ns)
    net.add_host(a)
    net.add_host(b)
    net.add_host(c)
    net.add_host(d)
    net.connect("a", "b", "10.0.0.0/30", 50000)
    net.connect("b", "c", "10.0.0.4/30", 50001)
    net.connect("c", "d", "10.0.0.8/30", 50002)
    net.connect("d", "a", "10.0.0.12/30", 50003)

    testbed.up()
    net.up()
    
    # 10.0.0.6 is c's ip
    # if it is reachable, then it means Network() can automatically compute routes to all local ips in the network
    assert(os.system(a_ns.gen_cmd("ping 10.0.0.6 -c 1")) == 0)

    assert(os.system(b_ns.gen_cmd("ping 10.0.0.13 -c 1")) == 0)
    assert(os.system(c_ns.gen_cmd("ping 10.0.0.1 -c 1")) == 0)

    net.down()
    testbed.down()