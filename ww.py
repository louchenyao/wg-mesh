#! /usr/bin/env python3

import json
import os
import subprocess


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


class Link(object):
    # `link_cidr` should be `/30`, namely, the last digit of ip is the multiple of 4
    # Suppose the `link_cidr="192.10.1.0", then the `left_ip` will be `192.10.1.1`,
    # the `right_ip` will be `192.10.1.2`.
    def __init__(self, left_key, right_key, right_wan_ip, link_cidr, port, mtu=1420):
        # check if the last digit is the multiple of 4
        abc = ".".join(link_cidr.split(".")[:3])
        d = int(link_cidr.split(".")[-1])
        assert(d % 4 == 0)

        self.left_key = left_key
        self.right_key = right_key
        self.left_ip = f"{abc}.{d+1}"
        self.right_ip = f"{abc}.{d+2}"
        self.right_endpoint = f"{right_wan_ip}:{port}"
        self.link_cidr = link_cidr
        self.port = port
        self.mtu = mtu

    def generate_left_config(self, dns):
        if dns:
            dns = f"\nDNS = {dns}"
        else:
            dns = ""

        return f"""[Interface]
PrivateKey = {self.left_key.sk}
Address = {self.left_ip}/30{dns}
MTU = {self.mtu}

[Peer]
PublicKey = {self.right_key.pk}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {self.right_endpoint}
PersistentKeepalive = 30
"""

    def generate_right_config(self):
        return f"""[Interface]
PrivateKey = {self.right_key.sk}
Address = {self.right_ip}/30
ListenPort = {self.port}
MTU = {self.mtu}

[Peer]
PublicKey = {self.left_key.pk}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 30
"""


class Host(object):
    def __init__(self, hostname, wan_ip, lo_ip, lo_ns_ip, home=None, key=None):
        self.hostname = hostname
        self.wan_ip = wan_ip
        self.lo_ip = lo_ip
        self.lo_ns_ip = lo_ns_ip

        if len(hostname) < 1:
            raise Exception("Empty hostname.")
        if not key:
            key = Key()
        self.key = key
        self.commands = []

        self.ns_exec = "ip netns exec wgns "
        self.add_ns("wgns")

        self.add_veth("gw", "gw-vm", "10.233.233.1", "10.233.233.2", "wgns")
        self.add_iptable("nat", "POSTROUTING",
                         "-s 10.233.233.2/32 -j MASQUERADE")
        self.add_route("default", via="10.233.233.1", in_ns=True)
        self.add_iptable(
            "nat", "POSTROUTING", "-o gw-vm ! -s 10.233.233.2/32 -j MASQUERADE", in_ns=True)

        self.add_veth("ww", "ww-vm", lo_ip, lo_ns_ip, "wgns")

        if home:
            self.home = home
        else:
            self.home = os.environ.get("HOME", "/root")
        self.private_key_path = os.path.join(self.home, "wg-world_prikey")
        self.add_cmd("echo '%s' > %s" % (self.key.sk, self.private_key_path))

    def add_ns(self, name):
        self.add_cmd("ip netns del %s | true" % name)
        self.add_cmd("ip netns add %s" % name)

    def add_veth(self, host, vm, host_ip, vm_ip, vm_ns):
        ns_exec = "ip netns exec %s " % vm_ns
        self.add_cmd("ip link del %s | true" % host)
        self.add_cmd("ip link del %s | true" % vm)

        self.add_cmd("ip link add %s type veth peer name %s" % (host, vm))
        self.add_cmd("ip link set %s netns %s" % (vm, vm_ns))
        self.add_cmd("ip link set %s up" % host)
        self.add_cmd("ip addr add %s/32 dev %s" % (host_ip, host))
        self.add_cmd("ip route add %s dev %s" % (vm_ip, host))
        self.add_cmd(ns_exec + "ip link set %s up" % vm)
        self.add_cmd(ns_exec + "ip addr add %s/32 dev %s" % (vm_ip, vm))
        self.add_cmd(ns_exec + "ip route add %s dev %s" % (host_ip, vm))

    def add_cmd(self, cmd):
        self.commands.append(cmd)

    def connect(self, right, my_ip, right_ip, mtu, listen_port=None, endpoint=None):
        dev = "wg.to." + right.hostname

        self.add_cmd(self.ns_exec + "ip link del dev %s | true" % dev)
        self.add_cmd(self.ns_exec + "ip link add dev %s type wireguard" % dev)
        self.add_cmd(self.ns_exec + "ip address add dev %s %s/30" %
                     (dev, my_ip))
        self.add_cmd(self.ns_exec + "ip link set mtu %s dev %s" % (mtu, dev))
        if listen_port:
            self.add_iptable(
                "nat", "PREROUTING", f"-p udp --dport {listen_port} -j DNAT --to-destination 10.233.233.2")
            self.add_cmd(
                self.ns_exec
                + f"wg set {dev} listen-port {listen_port} private-key {self.private_key_path}"
                + f" peer {right.key.pk} allowed-ips 0.0.0.0/0 persistent-keepalive 30"
            )
        else:
            self.add_cmd(
                self.ns_exec
                + f"wg set {dev} private-key {self.private_key_path} peer {right.key.pk}"
                + f" allowed-ips 0.0.0.0/0 endpoint {endpoint} persistent-keepalive 30"
            )

        self.add_iptable("mangle", "POSTROUTING",
                         "-o %s -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu" % dev, in_ns=True)
        self.add_cmd(self.ns_exec + "ip link set up dev %s" % dev)

    def cmds_str(self):
        s = ""
        for cmd in self.commands:
            s += cmd + "\n"
        return s

    def save_cmds_as_bash(self, name):
        with open(name, "w") as f:
            f.write("#! /bin/bash\n\nset -e\n\n")
            f.write(self.cmds_str())
        os.system("chmod +x %s" % name)

    def add_ipset(self, url, in_ns=False):
        ns_exec = self.ns_exec if in_ns else ""
        self.add_cmd("curl -o /tmp/ipset.txt " + url)
        self.add_cmd(ns_exec + "ipset --restore --exist < /tmp/ipset.txt")

    def add_iptable(self, table, chain, rule, in_ns=False):
        ns_exec = self.ns_exec if in_ns else ""
        self.add_cmd(ns_exec + "iptables -t %s -D %s %s | true" %
                     (table, chain, rule))
        self.add_cmd(ns_exec + "iptables -t %s -A %s %s" %
                     (table, chain, rule))

    def add_route(self, ip_ranges, in_ns, via=None, link=None):
        if type(ip_ranges) in [tuple, list]:
            for ip in ip_ranges:
                # it is not a ip range, so it is probably a domain
                self.add_route(ip, in_ns, via=via, link=link)
            return

        gw = None

        if via:
            gw = via
        elif link:
            if self.hostname == link.left.hostname:
                gw = link.right_ip
            elif self.hostname == link.right.hostname:
                gw = link.left_ip
            else:
                raise Exception("%s is not the endpoint of link %s" %
                                (self.hostname, link))
        else:
            raise Exception("Both via and link are None!")

        ns_exec = self.ns_exec if in_ns else ""
        self.add_cmd(ns_exec + "ip route del %s | true" % ip_ranges)
        self.add_cmd(ns_exec + "ip route add %s via %s" % (ip_ranges, gw))


if __name__ == "__main__":
    pass
