#! /usr/bin/env python3

from ww import *

def gen_key(d):
    Key().dump(f"{d}.key")

def yaoyao():
    # clients name
    clients = ["iPhone", "Macbook", "xzw", "lyh", "zhy", "qyx", "zys", "iPad", "lby", "zd-mac", "zd-phone", "zd-3", "zd-4"]

    # for c in clients:
    #     gen_key(c)
    # gen_key("dorm")
    # gen_key("bj")
    # gen_key("hk")

    # setup hosts
    dorm = Host("dorm", None, "10.56.100.3", "10.56.233.3", home="/home/louchenyao", key=Key(key_path="dorm.key"))
    bj = Host("bj", "bj.nossl.cn", "10.56.100.1", "10.56.233.1", home="/root", key=Key(key_path="bj.key"))
    hk = Host("hk", "hk.nossl.cn", "10.56.100.2", "10.56.233.2",home="/root", key=Key(key_path="hk.key"))
    clients_hosts = []
    for d in clients:
        clients_hosts.append(Host(d, None, None, None, key=Key(key_path=f"{d}.key")))

    # setup wireguard tunnels
    dorm_bj = Link(dorm, bj, mtu=1360)
    dorm_hk = Link(dorm, hk, mtu=1360)
    hk_bj = Link(hk, bj, mtu=1360)

    # clients to bj
    clients_links = []
    for d in clients_hosts:
        clients_links.append(Link(d, bj, mtu=1360))

    ################################
    # bj                           #
    ################################

    # route all wg-world ips into ww namespace
    bj.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24", "10.56.40.0/24", "1.1.1.1",], via=bj.lo_ns_ip, in_ns=False)
    # route hosts ip to the WAN
    bj.add_route(["bj.nossl.cn", "hk.nossl.cn"], via="10.233.233.1", in_ns=True)
    # route to hk
    bj.add_route([hk.lo_ip, hk.lo_ns_ip, "1.1.1.1"], link=hk_bj, in_ns=True)
    # route to dorm
    bj.add_route([dorm.lo_ip, dorm.lo_ns_ip, "10.56.40.0/24",], link=dorm_bj, in_ns=True)

    # for non-chinese ip, route them to hk
    bj.add_ipset("https://pppublic.oss-cn-beijing.aliyuncs.com/ipsets.txt", in_ns=True)
    bj.add_iptable("mangle", "PREROUTING", "-s 10.56.0.0/16 -m set ! --match-set china_ip dst -m set ! --match-set private_ip dst -j MARK --set-xmark 0x1/0xffffffff", in_ns=True)
    bj.add_cmd(bj.ns_exec + "ip rule add fwmark 0x1 table 100")
    bj.add_cmd(bj.ns_exec + "ip route add default via %s table 100" % hk_bj.left_ip)

    ################################
    # dorm                         #
    ################################
    dorm.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24"], via=dorm.lo_ns_ip, in_ns=False)
    dorm.add_route(["bj.nossl.cn", "hk.nossl.cn"], via="10.233.233.1", in_ns=True)
    dorm.add_route([hk.lo_ip, hk.lo_ns_ip, "1.1.1.1"], link=dorm_hk, in_ns=True)
    dorm.add_route([bj.lo_ip, bj.lo_ns_ip], link=dorm_bj, in_ns=True)
    dorm.add_route([d.left_ip for d in clients_links], link=dorm_bj, in_ns=True)
    dorm.add_route("10.56.40.0/24", via=dorm.lo_ip, in_ns=True)

    dorm.add_ipset("https://pppublic.oss-cn-beijing.aliyuncs.com/ipsets.txt", in_ns=True)
    dorm.add_iptable("mangle", "PREROUTING", "-s 10.56.0.0/16 -m set ! --match-set china_ip dst -m set ! --match-set private_ip dst -j MARK --set-xmark 0x1/0xffffffff", in_ns=True)
    dorm.add_cmd(dorm.ns_exec + "ip rule add fwmark 0x1 table 100")
    dorm.add_cmd(dorm.ns_exec + "ip route add default via %s table 100" % dorm_hk.right_ip)

    ################################
    # hk                           #
    ################################
    hk.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24", "10.56.40.0/24"], via=hk.lo_ns_ip, in_ns=False)
    hk.add_route(["bj.nossl.cn", "hk.nossl.cn"], via="10.233.233.1", in_ns=True)
    hk.add_route([dorm.lo_ip, dorm.lo_ns_ip, "10.56.40.0/24"], link=dorm_hk, in_ns=True)
    hk.add_route([bj.lo_ip, bj.lo_ns_ip], link=hk_bj, in_ns=True)
    hk.add_route([d.left_ip for d in clients_links], link=hk_bj, in_ns=True)
   
    # save configurations
    dorm.save_cmds_as_bash("dorm.sh")
    bj.save_cmds_as_bash("bj.sh")
    hk.save_cmds_as_bash("hk.sh")
    
    # friends configurations
    for link, name in zip(clients_links, clients):
        link.generate_left_config(f"{name}.conf")

if __name__ == "__main__":
    yaoyao()