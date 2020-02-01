#! /usr/bin/env python3

from mesh import *

import argparse
import signal
import sys 
import time

""" The example configuration also my personal private network configuration.
"""

key_dir = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "keys"
)

def gen_net(tmp_key):
    net = Network()

    if tmp_key:
        bj_key_path = None
        hk_key_path = None
    else:
        bj_key_path = os.path.join(key_dir, "bj.key")
        hk_key_path = os.path.join(key_dir, "hk.key")

    net.add_host(Host("bj", "39.96.60.177", Key(bj_key_path), global_ns))
    net.add_host(Host("hk", "47.91.154.79", Key(hk_key_path), global_ns))
    net.connect("bj", "hk", "10.56.1.0/30", 45677)

    clients_conf = [
        ("iPhone", "10.56.200.16/30", 45678),
        ("Macbook", "10.56.200.20/30", 45679),
        ("xzw", "10.56.200.24/30", 45680),
        ("lyh", "10.56.200.28/30", 45681),
        ("zhy", "10.56.200.32/30", 45682),
        ("qyx", "10.56.200.36/30", 45683),
        ("zys", "10.56.200.40/30", 45684),
        ("iPad", "10.56.200.44/30", 45685),
        ("lby", "10.56.200.48/30", 45686),
        ("zd-mac", "10.56.200.52/30", 45687),
        ("zd-phone", "10.56.200.56/30", 45688),
        ("zd-3", "10.56.200.60/30", 45689),
        ("zd-4", "10.56.200.64/30", 45690),
        ("gram", "10.56.200.68/30", 45691),
        ("wmd", "10.56.200.72/30", 45692),
    ]
    for c, cidr, port in clients_conf:
        if tmp_key:
            key_path = None
        else:
            key_path = os.path.join(key_dir, f"{c}.key")
        net.add_host(Host(c, "", Key(key_path), global_ns))
        net.connect(c, "bj", cidr, port)
    
    # define the non-china ipset bundle
    chinaip = IPSet("chinaip", chinaip_list(), global_ns)
    privateip = IPSet("privateip", privateip_list(), global_ns)
    nonchinaip = IPSetBundle(match=[], not_match=[chinaip, privateip])

    net.route_ipsetbundle_to_nat_gateway(nonchinaip, "bj", "hk")
    for c, _, _ in clients_conf:
        net.route_ipsetbundle_to_nat_gateway(nonchinaip, c, "hk")

    return net

class Killer(object):
    def __init__(self, net, host):
        self.net = net
        self.host = host
        signal.signal(signal.SIGINT, self.kill)
        signal.signal(signal.SIGTERM, self.kill)

    def kill(self, signum, frame):
        print("Shutting down...")
        self.net.down(self.host)
        sys.exit(0)

def mesh_main(gen):
    def get_hosts():
        tmp_net = gen(tmp_key=True)
        return [n for n in tmp_net.hosts]

    hosts = get_hosts()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='cmd')

    parser_up = subparsers.add_parser('up')
    parser_up.add_argument('host', type=str, choices=hosts)

    parser_genkey = subparsers.add_parser('genkey')
    assert('all' not in hosts) # all is a reserved host name
    parser_genkey.add_argument('host', type=str, choices=['all'] + hosts)

    args = parser.parse_args()

    if args.cmd == 'up':
        net = gen_net(tmp_key=False)
        net.up(args.host)
        print(f'Started as: {args.host}')
        killer = Killer(net, args.host)
        while True:
            time.sleep(1)

    if args.cmd == 'genkey':
        def gen_key(h):
            key_path = os.path.join(key_dir, f"{h}.key")
            assert(os.path.exists(key_path) == False)
            k = Key(None)
            k.dump(key_path)

        if args.host == 'all':
            for h in hosts: 
                gen_key(h)
        else:
            gen_key(args.host)

if __name__ == "__main__":
    mesh_main(gen_net)