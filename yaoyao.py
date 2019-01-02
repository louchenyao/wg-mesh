#! /usr/bin/env python3

from ww import Key, Host, Link

def yaoyao():
    # Key().dump("bj.key")
    # Key().dump("hk.key")
    # Key().dump("dorm.key")
    # Key().dump("iPhone.key")
    # Key().dump("mac.key")
    dorm_key = Key(key_path="dorm.key")
    hk_key = Key(key_path="hk.key")
    bj_key = Key(key_path="bj.key")
    iPhone_key = Key(key_path="iPhone.key")
    mac_key = Key(key_path="mac.key")

    dorm = Host("dorm", None, "10.56.100.3", "10.56.233.3", home="/home/louchenyao", key=dorm_key)
    bj = Host("bj", "bj.nossl.cn", "10.56.100.1", "10.56.233.1", home="/home/louchenyao", key=bj_key)
    hk = Host("hk", "hk.nossl.cn", "10.56.100.2", "10.56.233.2",home="/home/louchenyao", key=hk_key)

    iPhone = Host("iPhone", None, None, None, key=iPhone_key)
    mac = Host("mac", None, None, None, key=mac_key)

    dorm_bj = Link(dorm, bj, mtu=1420-80)
    dorm_hk = Link(dorm, hk, mtu=1420-80)
    hk_bj = Link(hk, bj)

    iPhone_bj = Link(iPhone, bj)
    mac_bj = Link(mac, bj)

    bj.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24", "10.56.40.0/24", "1.1.1.1",], via=bj.lo_ns_ip, in_ns=False)
    bj.add_route(["39.96.60.177", "47.75.6.103"], via="10.233.233.1", in_ns=True)
    bj.add_route([hk.lo_ip, hk.lo_ns_ip, "1.1.1.1"], link=hk_bj, in_ns=True)
    bj.add_route([dorm.lo_ip, dorm.lo_ns_ip], link=dorm_bj, in_ns=True)
    bj.add_route("10.56.40.0/24", link=dorm_bj, in_ns=True)

    bj.add_ipset("https://pppublic.oss-cn-beijing.aliyuncs.com/ipsets.txt", in_ns=True)
    bj.add_iptable("mangle", "PREROUTING", "-s 10.56.0.0/16 -m set ! --match-set china_ip dst -m set ! --match-set private_ip dst -j MARK --set-xmark 0x1/0xffffffff", in_ns=True)
    bj.add_cmd(bj.ns_exec + "ip rule add fwmark 0x1 table 100")
    bj.add_cmd(bj.ns_exec + "ip route add default via %s table 100" % hk_bj.right_ip)

    dorm.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24"], via=dorm.lo_ns_ip, in_ns=False)
    dorm.add_route(["39.96.60.177", "47.75.6.103"], via="10.233.233.1", in_ns=True)
    dorm.add_route([hk.lo_ip, hk.lo_ns_ip, "1.1.1.1"], link=dorm_hk, in_ns=True)
    dorm.add_route([bj.lo_ip, bj.lo_ns_ip], link=dorm_bj, in_ns=True)
    dorm.add_route([iPhone_bj.left_ip, mac_bj.left_ip], link=dorm_bj, in_ns=True)
    dorm.add_route("10.56.40.0/24", via=dorm.lo_ip, in_ns=True)

    dorm.add_ipset("https://pppublic.oss-cn-beijing.aliyuncs.com/ipsets.txt", in_ns=True)
    dorm.add_iptable("mangle", "PREROUTING", "-s 10.56.0.0/16 -m set ! --match-set china_ip dst -m set ! --match-set private_ip dst -j MARK --set-xmark 0x1/0xffffffff", in_ns=True)
    dorm.add_cmd(dorm.ns_exec + "ip rule add fwmark 0x1 table 100")
    dorm.add_cmd(dorm.ns_exec + "ip route add default via %s table 100" % dorm_hk.right_ip)
    #cmd("iptables -t mangle -A POSTROUTING -o wg0 -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu")

    hk.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24", "10.56.40.0/24"], via=hk.lo_ns_ip, in_ns=False)
    hk.add_route([dorm.lo_ip, dorm.lo_ns_ip], link=dorm_hk, in_ns=True)
    hk.add_route([bj.lo_ip, bj.lo_ns_ip], link=hk_bj, in_ns=True)
    hk.add_route([iPhone_bj.left_ip, mac_bj.left_ip], link=hk_bj, in_ns=True)
    hk.add_route("10.56.40.0/24", link=dorm_hk, in_ns=True)

    iPhone.save_cmds_as_bash("iPhone.sh")
    mac.save_cmds_as_bash("mac.sh")
    dorm.save_cmds_as_bash("dorm.sh")
    bj.save_cmds_as_bash("bj.sh")
    hk.save_cmds_as_bash("hk.sh")

if __name__ == "__main__":
    yaoyao()