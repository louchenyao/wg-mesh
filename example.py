#! /usr/bin/env python3

import cli
from mesh import *

""" The example configuration also my personal private network configuration.
"""

def gen_net(tmp_key: bool, mock_net: bool):
    net = Network(mock_net)

    net.add_host("bj", "39.96.60.177", cli.get_key("bj", tmp_key))
    net.add_host("hk", "47.244.57.178", cli.get_key("hk", tmp_key))
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
        net.add_host(c, "", cli.get_key(c, tmp_key))
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

    # freedns
    net.add_freedns("bj")

    return net

if __name__ == "__main__":
    cli.mesh_main(gen_net)