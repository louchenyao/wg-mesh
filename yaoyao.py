#! /usr/bin/env python3

from ww import Key, Host, Link

def yaoyao():
    # Key().dump("bj.key")
    # Key().dump("hk.key")
    # Key().dump("dorm.key")
    # Key().dump("iPhone.key")
    # Key().dump("mac.key")
    # Key().dump("lax.key")
    dorm_key = Key(key_path="dorm.key")
    lax_key = Key(key_path="lax.key")
    bj_key = Key(key_path="bj.key")
    iPhone_key = Key(key_path="iPhone.key")
    mac_key = Key(key_path="mac.key")

    dorm = Host("dorm", None, "10.56.100.3", "10.56.233.3", home="/home/louchenyao", key=dorm_key)
    bj = Host("bj", "bj.nossl.cn", "10.56.100.1", "10.56.233.1", home="/home/louchenyao", key=bj_key)
    #hk = Host("hk", "hk.nossl.cn", "10.56.100.2", "10.56.233.2",home="/home/louchenyao", key=hk_key)
    lax = Host("lax", "lax.nossl.cn", "10.56.100.4", "10.56.233.4",home="/home/louchenyao", key=lax_key)

    iPhone = Host("iPhone", None, None, None, key=iPhone_key)
    mac = Host("mac", None, None, None, key=mac_key)

    dorm_bj = Link(dorm, bj, mtu=1360)
    dorm_lax = Link(dorm, lax, mtu=1360)
    lax_bj = Link(lax, bj, mtu=1360)

    iPhone_bj = Link(iPhone, bj, mtu=1360)
    mac_bj = Link(mac, bj, mtu=1360)

    bj.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24", "10.56.40.0/24", "1.1.1.1",], via=bj.lo_ns_ip, in_ns=False)
    bj.add_route(["39.96.60.177", "89.208.248.29"], via="10.233.233.1", in_ns=True)
    bj.add_route([lax.lo_ip, lax.lo_ns_ip, "1.1.1.1"], link=lax_bj, in_ns=True)
    bj.add_route([dorm.lo_ip, dorm.lo_ns_ip, "10.56.40.0/24",], link=dorm_bj, in_ns=True)

    bj.add_ipset("https://pppublic.oss-cn-beijing.aliyuncs.com/ipsets.txt", in_ns=True)
    bj.add_iptable("mangle", "PREROUTING", "-s 10.56.0.0/16 -m set ! --match-set china_ip dst -m set ! --match-set private_ip dst -j MARK --set-xmark 0x1/0xffffffff", in_ns=True)
    bj.add_cmd(bj.ns_exec + "ip rule add fwmark 0x1 table 100")
    bj.add_cmd(bj.ns_exec + "ip route add default via %s table 100" % lax_bj.left_ip)

    dorm.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24"], via=dorm.lo_ns_ip, in_ns=False)
    dorm.add_route(["39.96.60.177", "89.208.248.29"], via="10.233.233.1", in_ns=True)
    dorm.add_route([lax.lo_ip, lax.lo_ns_ip, "1.1.1.1"], link=dorm_lax, in_ns=True)
    dorm.add_route([bj.lo_ip, bj.lo_ns_ip], link=dorm_bj, in_ns=True)
    dorm.add_route([iPhone_bj.left_ip, mac_bj.left_ip], link=dorm_bj, in_ns=True)
    dorm.add_route("10.56.40.0/24", via=dorm.lo_ip, in_ns=True)

    dorm.add_ipset("https://pppublic.oss-cn-beijing.aliyuncs.com/ipsets.txt", in_ns=True)
    dorm.add_iptable("mangle", "PREROUTING", "-s 10.56.0.0/16 -m set ! --match-set china_ip dst -m set ! --match-set private_ip dst -j MARK --set-xmark 0x1/0xffffffff", in_ns=True)
    dorm.add_cmd(dorm.ns_exec + "ip rule add fwmark 0x1 table 100")
    dorm.add_cmd(dorm.ns_exec + "ip route add default via %s table 100" % dorm_lax.right_ip)
    #cmd("iptables -t mangle -A POSTROUTING -o wg0 -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu")

    lax.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24", "10.56.40.0/24"], via=lax.lo_ns_ip, in_ns=False)
    lax.add_route([dorm.lo_ip, dorm.lo_ns_ip, "10.56.40.0/24"], link=dorm_lax, in_ns=True)
    lax.add_route([bj.lo_ip, bj.lo_ns_ip], link=lax_bj, in_ns=True)
    lax.add_route([iPhone_bj.left_ip, mac_bj.left_ip], link=lax_bj, in_ns=True)

    iPhone.save_cmds_as_bash("iPhone.sh")
    mac.save_cmds_as_bash("mac.sh")
    dorm.save_cmds_as_bash("dorm.sh")
    bj.save_cmds_as_bash("bj.sh")
    lax.save_cmds_as_bash("lax.sh")

if __name__ == "__main__":
    yaoyao()