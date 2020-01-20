#! /usr/bin/env python3

import json
import os
import requests
import subprocess
import tempfile


class Key(object):
    def __init__(self, key_path):
        if key_path:
            self.load(key_path)
        else:
            self.sk = subprocess.getoutput("wg genkey")
            self.pk = subprocess.getoutput("echo '%s' | wg pubkey" % self.sk)

    def __str__(self):
        return "<PubKey: %s, PriKey: ******>" % self.pk

    def dump(self, path):
        with open(path, "w") as f:
            f.write(json.dumps({"sk": self.sk, "pk": self.pk}))

    def load(self, path):
        with open(path) as f:
            j = json.loads(f.read())
            self.pk = j["pk"]
            self.sk = j["sk"]


class NS(object):
    def __init__(self, ns_name):
        self.ns_name = ns_name

    def gen_cmd(self, cmd):
        if self.ns_name == "__global_ns":
            return f"sudo {cmd}"
        else:
            return f"sudo ip netns exec {self.ns_name} {cmd}"

    def up(self):
        if self.ns_name != "__global_ns":
            assert(os.system(f"sudo ip netns add {self.ns_name}") == 0)

    def down(self):
        if self.ns_name != "__global_ns":
            assert(os.system(f"sudo ip netns del {self.ns_name}") == 0)


global_ns = NS("__global_ns")


class Veth(object):
    def __init__(self, name, left_addr, right_addr, left_ns, right_ns):
        self.up_cmds = [
            left_ns.gen_cmd(
                f"ip link add {name}-left type veth peer name {name}-right"),
            left_ns.gen_cmd(
                f"ip link set {name}-right netns {right_ns.ns_name}"),
            left_ns.gen_cmd(f"ip link set {name}-left up"),
            left_ns.gen_cmd(f"ip addr add {left_addr} dev {name}-left"),

            right_ns.gen_cmd(f"ip link set {name}-right up"),
            right_ns.gen_cmd(f"ip addr add {right_addr} dev {name}-right"),
        ]

        self.down_cmds = [
            # delete one is enough
            left_ns.gen_cmd(f"ip link del {name}-left"),
        ]

    def up(self):
        for c in self.up_cmds:
            assert(os.system(c) == 0)

    def down(self):
        for c in self.down_cmds:
            assert(os.system(c) == 0)


class Wg(object):
    def __init__(self, is_right: bool, name: str, left_key: Key, right_key: Key, addr: str,
                 right_wan_ip: str, port: int, mtu: int, ns: NS):
        self.name = name
        self.ns = ns

        self.tmp_dir = tempfile.mkdtemp()
        sk_p = os.path.join(self.tmp_dir, "sk")
        with open(sk_p, "w") as f:
            if is_right:
                f.write(right_key.sk)
            else:
                f.write(left_key.sk)

        self.up_cmds = [
            ns.gen_cmd(f"ip link add dev {name} type wireguard"),
            ns.gen_cmd(f"ip address add dev {name} {addr}"),
            ns.gen_cmd(f"ip link set mtu {mtu} dev {name}"),
        ]

        if is_right:
            self.up_cmds.append(
                ns.gen_cmd(f"wg set {name} listen-port {port} private-key {sk_p}"
                           + f" peer {left_key.pk} allowed-ips 0.0.0.0/0 persistent-keepalive 30")
            )
        else:
            self.up_cmds.append(
                ns.gen_cmd(f"wg set {name} private-key {sk_p}"
                           + f" peer {right_key.pk} endpoint {right_wan_ip}:{port}"
                           + f" allowed-ips 0.0.0.0/0  persistent-keepalive 30")
            )

        self.up_cmds.append(ns.gen_cmd(f"ip link set up dev {name}"))
        self.down_cmd = ns.gen_cmd(f"ip link del {name}")

    def up(self):
        for c in self.up_cmds:
            assert(os.system(c) == 0)

    def down(self):
        assert(os.system(self.down_cmd) == 0)
        assert(os.system(f"rm -r {self.tmp_dir}") == 0)


# `link_cidr` should be `/30`, namely, the last digit of ip is the multiple of 4
# Suppose the `link_cidr="192.10.1.0/30", then the `left_ip` will be `192.10.1.1`,
# the `right_ip` will be `192.10.1.2`.
def gen_wg(name, left_key, right_key, right_wan_ip, link_cidr, port, mtu, left_ns, right_ns):
    # check if the last digit is the multiple of 4
    assert(link_cidr.endswith("/30"))
    abcd = link_cidr[:-3]
    abc = ".".join(abcd.split(".")[:3])
    d = int(abcd.split(".")[-1])
    assert(d % 4 == 0)

    left_ip = f"{abc}.{d+1}/30"
    right_ip = f"{abc}.{d+2}/30"

    left = Wg(False, name, left_key, right_key, left_ip,
              right_wan_ip, int(port), int(mtu), left_ns)
    right = Wg(True, name, left_key, right_key, right_ip,
               right_wan_ip, int(port), int(mtu), right_ns)

    return left, right


class IPTableRule(object):
    def __init__(self, table, chain, rule, ns: NS):
        self.up_cmd = ns.gen_cmd(f"iptables -t {table} -A {chain} {rule}")
        self.down_cmd = ns.gen_cmd(f"iptables -t {table} -D {chain} {rule}")

    def up(self):
        assert(os.system(self.up_cmd) == 0)

    def down(self):
        assert(os.system(self.down_cmd) == 0)


class Route(object):
    def __init__(self, addr, via, table, ns: NS):
        self.up_cmd = ns.gen_cmd(f"ip route add {addr} via {via} table {table}")
        self.down_cmd = ns.gen_cmd(f"ip route del {addr} via {via} table {table}")

    def up(self):
        assert(os.system(self.up_cmd) == 0)

    def down(self):
        assert(os.system(self.down_cmd) == 0)

class RouteRule(object):
    def __init__(self, mark, table, ns: NS):
        self.mark = mark
        self.table = table
        self.ns = ns
    
    def up(self):
        assert(os.system(self.ns.gen_cmd(f"ip rule add fwmark {self.mark} {self.table}")) == 0)
    
    def down(self):
        assert(os.system(self.ns.gen_cmd(f"ip rule del fwmark {self.mark} {self.table}")) == 0)

class IPSet(object):
    def __init__(self, name: str, ips: list, ns: NS):
        self.create = ns.gen_cmd(f"ipset create {name} hash:net")
        self.destroy = ns.gen_cmd(f"ipset destroy {name}")
        self.name = name
        self.ns = ns
        self.ips = ips

        self.ipset_txt = ""
        for ip in self.ips:
            self.ipset_txt += f"add {name} {ip}\n"

    def up(self):
        assert(os.system(self.create) == 0)
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = os.path.join(tmp_dir, "ipset.txt")
            with open(p, "w") as f:
                f.write(self.ipset_txt)
            assert(os.system(self.ns.gen_cmd(f"ipset restore < {p}")) == 0)

    def down(self):
        assert(os.system(self.destroy) == 0)


_china_ip_list_cache = []


def chinaip_list():
    global _china_ip_list_cache
    if len(_china_ip_list_cache) != 0:
        return _china_ip_list_cache

    r = requests.get(
        "https://raw.githubusercontent.com/17mon/china_ip_list/master/china_ip_list.txt")
    _china_ip_list_cache = r.text.split()
    return _china_ip_list_cache


def privateip_list():
    return ["192.168.0.0/16", "172.16.0.0/12", "10.0.0.0/8"]

# Net is a set of netowrk configs
class Net(object):
    def __init__(self):
        self.conf = []
    
    def add(self, c):
        if type(c) == list or type(c) == tuple:
            self.conf += c
        else:
            self.conf.append(c)
        
    
    def up(self):
        for c in self.conf:
            c.up()

    def down(self):
        for c in self.conf[::-1]:
            c.down()

# class Host(object):
#     def __init__(self, hostname, wan_ip, lo_ip, lo_ns_ip, home=None, key=None):
#         self.hostname = hostname
#         self.wan_ip = wan_ip
#         self.lo_ip = lo_ip
#         self.lo_ns_ip = lo_ns_ip

#         if len(hostname) < 1:
#             raise Exception("Empty hostname.")
#         if not key:
#             key = Key()
#         self.key = key
#         self.commands = []

#         self.ns_exec = "ip netns exec wgns "
#         self.add_ns("wgns")

#         self.add_veth("gw", "gw-vm", "10.233.233.1", "10.233.233.2", "wgns")
#         self.add_iptable("nat", "POSTROUTING",
#                          "-s 10.233.233.2/32 -j MASQUERADE")
#         self.add_route("default", via="10.233.233.1", in_ns=True)
#         self.add_iptable(
#             "nat", "POSTROUTING", "-o gw-vm ! -s 10.233.233.2/32 -j MASQUERADE", in_ns=True)

#         self.add_veth("ww", "ww-vm", lo_ip, lo_ns_ip, "wgns")

#         if home:
#             self.home = home
#         else:
#             self.home = os.environ.get("HOME", "/root")
#         self.private_key_path = os.path.join(self.home, "wg-world_prikey")
#         self.add_cmd("echo '%s' > %s" % (self.key.sk, self.private_key_path))

#     def add_ns(self, name):
#         self.add_cmd("ip netns del %s | true" % name)
#         self.add_cmd("ip netns add %s" % name)

#     def add_veth(self, host, vm, host_ip, vm_ip, vm_ns):
#         ns_exec = "ip netns exec %s " % vm_ns
#         self.add_cmd("ip link del %s | true" % host)
#         self.add_cmd("ip link del %s | true" % vm)

#         self.add_cmd("ip link add %s type veth peer name %s" % (host, vm))
#         self.add_cmd("ip link set %s netns %s" % (vm, vm_ns))
#         self.add_cmd("ip link set %s up" % host)
#         self.add_cmd("ip addr add %s/32 dev %s" % (host_ip, host))
#         self.add_cmd("ip route add %s dev %s" % (vm_ip, host))
#         self.add_cmd(ns_exec + "ip link set %s up" % vm)
#         self.add_cmd(ns_exec + "ip addr add %s/32 dev %s" % (vm_ip, vm))
#         self.add_cmd(ns_exec + "ip route add %s dev %s" % (host_ip, vm))

#     def add_cmd(self, cmd):
#         self.commands.append(cmd)

#     def connect(self, right, my_ip, right_ip, mtu, listen_port=None, endpoint=None):
#         dev = "wg.to." + right.hostname

#         self.add_cmd(self.ns_exec + "ip link del dev %s | true" % dev)
#         self.add_cmd(self.ns_exec + "ip link add dev %s type wireguard" % dev)
#         self.add_cmd(self.ns_exec + "ip address add dev %s %s/30" %
#                      (dev, my_ip))
#         self.add_cmd(self.ns_exec + "ip link set mtu %s dev %s" % (mtu, dev))
#         if listen_port:
#             self.add_iptable(
#                 "nat", "PREROUTING", f"-p udp --dport {listen_port} -j DNAT --to-destination 10.233.233.2")
#             self.add_cmd(
#                 self.ns_exec
#                 + f"wg set {dev} listen-port {listen_port} private-key {self.private_key_path}"
#                 + f" peer {right.key.pk} allowed-ips 0.0.0.0/0 persistent-keepalive 30"
#             )
#         else:
#             self.add_cmd(
#                 self.ns_exec
#                 + f"wg set {dev} private-key {self.private_key_path} peer {right.key.pk}"
#                 + f" allowed-ips 0.0.0.0/0 endpoint {endpoint} persistent-keepalive 30"
#             )

#         self.add_iptable("mangle", "POSTROUTING",
#                          "-o %s -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu" % dev, in_ns=True)
#         self.add_cmd(self.ns_exec + "ip link set up dev %s" % dev)

#     def cmds_str(self):
#         s = ""
#         for cmd in self.commands:
#             s += cmd + "\n"
#         return s

#     def save_cmds_as_bash(self, name):
#         with open(name, "w") as f:
#             f.write("#! /bin/bash\n\nset -e\n\n")
#             f.write(self.cmds_str())
#         os.system("chmod +x %s" % name)

#     def add_ipset(self, url, in_ns=False):
#         ns_exec = self.ns_exec if in_ns else ""
#         self.add_cmd("curl -o /tmp/ipset.txt " + url)
#         self.add_cmd(ns_exec + "ipset --restore --exist < /tmp/ipset.txt")

#     def add_iptable(self, table, chain, rule, in_ns=False):
#         ns_exec = self.ns_exec if in_ns else ""
#         self.add_cmd(ns_exec + "iptables -t %s -D %s %s | true" %
#                      (table, chain, rule))
#         self.add_cmd(ns_exec + "iptables -t %s -A %s %s" %
#                      (table, chain, rule))

#     def add_route(self, ip_ranges, in_ns, via=None, link=None):
#         if type(ip_ranges) in [tuple, list]:
#             for ip in ip_ranges:
#                 # it is not a ip range, so it is probably a domain
#                 self.add_route(ip, in_ns, via=via, link=link)
#             return

#         gw = None

#         if via:
#             gw = via
#         elif link:
#             if self.hostname == link.left.hostname:
#                 gw = link.right_ip
#             elif self.hostname == link.right.hostname:
#                 gw = link.left_ip
#             else:
#                 raise Exception("%s is not the endpoint of link %s" %
#                                 (self.hostname, link))
#         else:
#             raise Exception("Both via and link are None!")

#         ns_exec = self.ns_exec if in_ns else ""
#         self.add_cmd(ns_exec + "ip route del %s | true" % ip_ranges)
#         self.add_cmd(ns_exec + "ip route add %s via %s" % (ip_ranges, gw))


if __name__ == "__main__":
    pass
