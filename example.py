#! /usr/bin/env python3

import cli
from mesh import *

""" The example configuration also my personal private network configuration.
"""

def gen_net(tmp_key):
    net = Network()

    if tmp_key:
        bj_key_path = None
        hk_key_path = None
    else:
        bj_key_path = os.path.join(cli.key_dir, "bj.key")
        hk_key_path = os.path.join(cli.key_dir, "hk.key")

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
            key_path = os.path.join(cli.key_dir, f"{c}.key")
        net.add_host(Host(c, "", Key(key_path), global_ns))
        net.connect(c, "bj", cidr, port)
    
    # define the ipset bundles
    chinaip = IPSet("chinaip", chinaip_list(), global_ns)
    privateip = IPSet("privateip", privateip_list(), global_ns)
    chinaip_bundle = IPSetBundle(match=[chinaip], not_match=[])
    nonchinaip_bundle = IPSetBundle(match=[], not_match=[chinaip, privateip])

    net.route_ipsetbundle_to_nat_gateway(nonchinaip_bundle, "bj", "hk")
    for c, _, _ in clients_conf:
        net.route_ipsetbundle_to_nat_gateway(chinaip_bundle, c, "bj")
        net.route_ipsetbundle_to_nat_gateway(nonchinaip_bundle, c, "hk")

    return net

if __name__ == "__main__":
    cli.mesh_main(gen_net)