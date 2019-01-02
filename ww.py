#! /usr/bin/env python3

import json
import os
import random
import subprocess

PORT = 45674
IP = 0

class Key(object):
    def __init__(self, sk = None, pk = None, key_path=None):
        if key_path:
            self.load(key_path)
        elif not pk:
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
    

class Host(object):
    def __init__(self, hostname, address, lo_ip, lo_ns_ip, home = None, key = None):
        self.hostname = hostname
        self.address = address
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
        self.add_iptable("nat", "POSTROUTING", "-s 10.233.233.2/32 -j MASQUERADE")
        self.add_route("default", via="10.233.233.1", in_ns=True)
        self.add_iptable("nat", "POSTROUTING", "-o gw-vm ! -d 10.233.233.2/32 -j MASQUERADE", in_ns=True)

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
        dev = "wg.to." +right.hostname

        self.add_cmd(self.ns_exec + "ip link del dev %s | true" % dev)
        self.add_cmd(self.ns_exec + "ip link add dev %s type wireguard" % dev)
        self.add_cmd(self.ns_exec + "ip address add dev %s %s/30" % (dev, my_ip))
        self.add_cmd(self.ns_exec + "ip link set mtu %s dev %s" % (mtu, dev))
        if listen_port:
            self.add_iptable("nat", "PREROUTING", "-p udp --dport %d -j DNAT --to-destination 10.233.233.2" % listen_port)
            self.add_cmd(self.ns_exec + "wg set %s listen-port %d private-key %s peer %s allowed-ips 0.0.0.0/0 persistent-keepalive 30" % (dev, listen_port, self.private_key_path, right.key.pk))
        else:
            self.add_cmd(self.ns_exec + "wg set %s private-key %s peer %s allowed-ips 0.0.0.0/0 endpoint %s persistent-keepalive 30" % (dev, self.private_key_path, right.key.pk, endpoint))
        self.add_iptable("mangle", "POSTROUTING", "-o %s -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu" % dev, in_ns=True)
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

    def add_iptable(self, table, chain, rule, in_ns = False):
        ns_exec = self.ns_exec if in_ns else ""
        self.add_cmd(ns_exec + "iptables -t %s -D %s %s | true" % (table, chain, rule))
        self.add_cmd(ns_exec + "iptables -t %s -A %s %s" % (table, chain, rule))

    def add_route(self, ip_range, in_ns, via=None, link=None):
        if type(ip_range) in [tuple, list]:
            for ip in ip_range:
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
                raise Exception("%s is not the endpoint of link %s" % (self.hostname, link))
        else:
            raise Exception("Both via and link are None!")

        ns_exec = self.ns_exec if in_ns else ""
        self.add_cmd(ns_exec + "ip route del %s | true" % ip_range)
        self.add_cmd(ns_exec + "ip route add %s via %s" % (ip_range, gw))

class Link(object):
    def __init__(self, left, right, mtu=1420):
        global PORT, IP
        PORT += 1
        IP += 4
        left_ip = "10.56.200.%d" % (IP+1)
        right_ip = "10.56.200.%d" % (IP+2)
        left.connect(right, left_ip, right_ip, mtu=mtu, endpoint=right.address+":"+str(PORT))
        right.connect(left, right_ip, left_ip, mtu=mtu, listen_port=PORT)

        self.left = left
        self.left_ip = left_ip
        self.right = right
        self.right_ip = right_ip

if __name__ == "__main__":
    pass
