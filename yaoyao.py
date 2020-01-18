#! /usr/bin/env python3

from ww import *
import shutil

def gen_key(d):
    Key().dump(f"keys/{d}.key")

def yaoyao():
    # clients name
    clients = ["iPhone", "Macbook", "xzw", "lyh", "zhy", "qyx", "zys", "iPad", "lby", "zd-mac", "zd-phone", "zd-3", "zd-4", "gram", "wmd"]

    # setup hosts
    bj = Host("bj", "bj.nossl.cn", "10.56.100.1", "10.56.233.1", home="/root", key=Key(key_path="keys/bj.key"))
    hk = Host("hk", "hk.nossl.cn", "10.56.100.2", "10.56.233.2",home="/root", key=Key(key_path="keys/hk.key"))
    clients_hosts = []
    for d in clients:
        clients_hosts.append(Host(d, None, None, None, key=Key(key_path=f"keys/{d}.key")))

    # setup wireguard tunnels
    hk_bj = Link(hk, bj, cidr="10.56.200.12", port="45677", mtu=1360)

    # clients to bj
    clients_links = []
    cidr_d = 12
    port = 45677
    for d in clients_hosts:
        cidr_d += 4
        port += 1
        clients_links.append(Link(d, bj, cidr=f"10.56.200.{cidr_d}", port=port, mtu=1360))

    ################################
    # bj                           #
    ################################

    # route all wg-world ips into ww namespace
    bj.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24", "10.56.40.0/24", "1.1.1.1",], via=bj.lo_ns_ip, in_ns=False)
    # route hosts ip to the WAN
    bj.add_route(["bj.nossl.cn", "hk.nossl.cn"], via="10.233.233.1", in_ns=True)
    # route to hk
    bj.add_route([hk.lo_ip, hk.lo_ns_ip, "1.1.1.1"], link=hk_bj, in_ns=True)

    # for non-chinese ip, route them to hk
    bj.add_ipset("https://pppublic.oss-cn-beijing.aliyuncs.com/ipsets.txt", in_ns=True)
    bj.add_iptable("mangle", "PREROUTING", "-s 10.56.0.0/16 -m set ! --match-set china_ip dst -m set ! --match-set private_ip dst -j MARK --set-xmark 0x1/0xffffffff", in_ns=True)
    bj.add_cmd(bj.ns_exec + "ip rule add fwmark 0x1 table 100")
    bj.add_cmd(bj.ns_exec + "ip route add default via %s table 100" % hk_bj.left_ip)

    ################################
    # hk                           #
    ################################
    hk.add_route(["10.56.100.0/24", "10.56.200.0/24", "10.56.233.0/24", "10.56.40.0/24"], via=hk.lo_ns_ip, in_ns=False)
    hk.add_route(["bj.nossl.cn", "hk.nossl.cn"], via="10.233.233.1", in_ns=True)
    hk.add_route([bj.lo_ip, bj.lo_ns_ip], link=hk_bj, in_ns=True)
    hk.add_route([d.left_ip for d in clients_links], link=hk_bj, in_ns=True)
   
    # save configurations
    shutil.rmtree("generated", ignore_errors=True)
    os.mkdir("generated")
    bj.save_cmds_as_bash("generated/bj.sh")
    hk.save_cmds_as_bash("generated/hk.sh")
    
    # friends configurations
    for link, name in zip(clients_links, clients):
        link.generate_left_config(f"generated/{name}.conf")

if __name__ == "__main__":
    yaoyao()