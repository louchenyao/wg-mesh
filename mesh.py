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
        self.addr = addr

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
            # the encrypted wireguard traffic will be marked with 51820
            ns.gen_cmd(f"wg set {name} fwmark 51820"),
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

    def __del__(self):
        assert(os.system(f"rm -r {self.tmp_dir}") == 0)

    def up(self):
        for c in self.up_cmds:
            assert(os.system(c) == 0)

    def down(self):
        assert(os.system(self.down_cmd) == 0)


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
        #print(f"+ {self.up_cmd}")
        assert(os.system(self.up_cmd) == 0)

    def down(self):
        assert(os.system(self.down_cmd) == 0)


class Route(object):
    def __init__(self, addr, via, table, ns: NS):
        self.up_cmd = ns.gen_cmd(f"ip route add {addr} via {via} table {table}")
        self.down_cmd = ns.gen_cmd(f"ip route del {addr} via {via} table {table}")

    def up(self):
        #print(f"+ {self.up_cmd}")
        assert(os.system(self.up_cmd) == 0)

    def down(self):
        assert(os.system(self.down_cmd) == 0)

class RouteRule(object):
    def __init__(self, mark, table, ns: NS):
        self.mark = mark
        self.table = table
        self.ns = ns
    
    def up(self):
        assert(os.system(self.ns.gen_cmd(f"ip rule add fwmark {self.mark} table {self.table}")) == 0)
    
    def down(self):
        assert(os.system(self.ns.gen_cmd(f"ip rule del fwmark {self.mark} table {self.table}")) == 0)

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
        "https://pppublic.oss-cn-beijing.aliyuncs.com/china_ip_list.txt")
    _china_ip_list_cache = r.text.split()
    return _china_ip_list_cache


def privateip_list():
    return ["192.168.0.0/16", "172.16.0.0/12", "10.0.0.0/8"]


class IPSetBundle(object):
    def __init__(self, match: tuple, not_match: tuple):
        self.match = match
        self.not_match = not_match
    
    def gen_iptables_condition(self):
        s = ""
        for m in self.match:
            s += f"-m set --match-set {m.name} dst "
        for m in self.not_match:
            s += f"-m set ! --match-set {m.name} dst "
        return s.strip()

class AnyProxy(object):
    def up(self):
        assert(os.system("ulimit -n 65535") == 0)
        bin = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "bin",
            "any_proxy",
        )
        self.p = subprocess.Popen([bin, '-l=:3140'])
    
    def down(self):
        self.p.terminate()


# ConfSet is a set of netowrk configs
class ConfSet(object):
    def __init__(self):
        self.conf = []
    
    def add(self, c):
        if type(c) == list or type(c) == tuple:
            self.conf += c
        else:
            self.conf.append(c)

    def add_begin(self, c):
        self.conf = [c] + self.conf
    
    def up(self):
        succ = []
        for c in self.conf:
            try:
                c.up()
            except Exception as e:
                # roll back
                for c in succ[::-1]:
                    c.down()
                raise e
            succ.append(c)

    def down(self):
        for c in self.conf[::-1]:
            c.down()


class Host(object):
    def __init__(self, name: str, wan_ip: str, key: Key, ns: NS):
        self.name = name
        self.wan_ip = wan_ip
        self.key = key
        self.ns = ns
        self.confs = ConfSet()
        self.ipsets_in_confs = {}
        self.lan_cidrs = []

        self.route_table_counter = 100

    # claim the cidr that is reachable from this host
    def claim_lan_cidr(self, cidr):
        self.lan_cidrs.append(cidr)
    
    def add_ipset(self, ipset):
        if ipset.name not in self.ipsets_in_confs:
            # reconstruct it to make sure the ipset is in self.ns
            ipset = IPSet(ipset.name, ipset.ips, self.ns)
            self.confs.add_begin(ipset)
            self.ipsets_in_confs[ipset.name] = True

    def policy_route(self, local_output: bool, nat_gateway: bool, src_ip: str, ipsetbundle: IPSetBundle, next_hop: str):
        assert(not(local_output and nat_gateway))

        route_table = self.route_table_counter
        self.route_table_counter += 1

        bundle_cond = ipsetbundle.gen_iptables_condition()
        match_src =f"-s {src_ip}"
        mark_0 = "-m mark --mark 0"
        not_established= "-m state ! --state ESTABLISHED,RELATED"
        target = f"-j MARK --set-mark {route_table}"

        if local_output:
            # important:
            # uses connmark to track the connection so for the traffic originating from the outside won't go through the table
            # test cases may not test this well! Be careful when making change.
            self.confs.add(IPTableRule("mangle", "OUTPUT", f"{bundle_cond} {mark_0} {not_established} -j CONNMARK --set-mark {route_table}", self.ns))
            self.confs.add(IPTableRule("mangle", "OUTPUT", f"-m connmark --mark {route_table} {target}", self.ns)) # equals to `-j restore-mark`
            self.confs.add(IPTableRule("nat", "POSTROUTING", f"-m mark --mark {route_table} -j SNAT --to-source {src_ip}", self.ns))
        elif not nat_gateway:
            self.confs.add(IPTableRule("mangle", "PREROUTING", f"{bundle_cond} {mark_0} {match_src} {target}", self.ns))
        else:
            self.confs.add(IPTableRule("nat", "POSTROUTING", f"{bundle_cond} {mark_0} {match_src}  -j MASQUERADE", self.ns))

        if not nat_gateway:
            self.confs.add(Route("default", next_hop, route_table, self.ns))
            self.confs.add(RouteRule(route_table, route_table, self.ns))

class Network(object):
    def __init__(self):
        self.hosts = {}
        self.edges = {}
        self.computed_routing_info = False

    def add_host(self, host):
        self.hosts[host.name] = host
        self.edges[host.name] = []

    def connect(self, left: str, right: str, cidr: str, port: int):
        left = self.hosts[left]
        right = self.hosts[right]

        lwg, rwg = gen_wg(
            name=f"{left.name}.{right.name}",
            left_key = left.key,
            right_key = right.key,
            right_wan_ip = right.wan_ip,
            link_cidr = cidr,
            port = port,
            mtu = 1320,
            left_ns = left.ns,
            right_ns = right.ns
        )
        left.confs.add(lwg)
        right.confs.add(rwg)
        lip = lwg.addr.split("/")[0]
        rip = rwg.addr.split("/")[0]
        left.claim_lan_cidr(lip)
        right.claim_lan_cidr(rip)
        self.edges[left.name].append([right.name, lip, rip])
        self.edges[right.name].append([left.name, rip, lip])

    def route_ipsetbundle_to_nat_gateway(self, ipsetbundle: IPSetBundle, src: str, gateway: str):
        # uses bfs to find a shortest path 
        def shortest_path(start: str, end: str):
            vis = {name: False for name in self.hosts}
            edges = {name: () for name in self.hosts}

            vis[start] = True
            q = [start]

            while len(q) > 0:
                u = q[0]
                q = q[1:]
                for v, tunnel_ip, next_hop in self.edges[u]:
                    if vis[v]:
                        continue
                    vis[v] = True
                    q.append(v)
                    edges[v] = (u, v, tunnel_ip, next_hop) # u -> v via next_hop

                    if v == end:
                        break
            
            assert(vis[v])
            # recover the path from `start` to `end`
            paths = []
            u = end
            while u != start:
                paths.append(edges[u])
                u = edges[u][0]
            paths = paths[::-1] # reverse edges
            return paths

        
        paths = shortest_path(src, gateway)
        #print(paths)

        # Add ipsets to the hosts on the path
        nodes = [paths[0][0],]
        for e in paths:
            nodes.append(e[1])
        for node in nodes:
            for ipset in ipsetbundle.match + ipsetbundle.not_match:
                self.hosts[node].add_ipset(ipset)

        # setup policy routing on the hosts
        src_ip = paths[0][2] # src_ip should be the tunnel ip on the `src` node 
        for i, (u, _, _, next_hop) in enumerate(paths):
            local_output = i == 0
            self.hosts[u].policy_route(local_output, False, src_ip, ipsetbundle, next_hop)
        self.hosts[gateway].policy_route(False, True, src_ip, ipsetbundle, "")

    def _compute_route(self):
        # only do this once
        if self.computed_routing_info:
            return
        self.computed_routing_info = True

        def compute_routeings(start):
            cidrs = self.hosts[start].lan_cidrs
            vis = {name: False for name in self.hosts}
            vis[start] = True
            q = [start]

            while len(q) > 0:
                u = q[0]
                q = q[1:]
                for v, next_hop, _ in self.edges[u]:
                    if vis[v]:
                        continue
                    vis[v] = True
                    q.append(v)

                    # connect
                    for cidr in cidrs:
                        if cidr != next_hop:
                            #print(f"{v} -> {cidr} via {next_hop}")
                            self.hosts[v].confs.add(Route(cidr, next_hop, "main", self.hosts[v].ns))

        # compute routing about from other hosts to self.hosts[name].cidrs
        for name in self.hosts:
            compute_routeings(name)

    def up(self, host: str):
        self._compute_route()
        self.hosts[host].confs.up()

    def down(self, host: str):
        self.hosts[host].confs.down()
