import argparse
import os
import signal
import sys
import time

from mesh import Key, Wg

key_dir = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "keys"
)

def get_key(host: str, tmp_key: bool):
    if tmp_key:
        return Key(None)
    else:
        return Key(os.path.join(key_dir, f"{host}.key"))


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
    tmp_net = gen(tmp_key=True, mock_net=False)
    hosts = [n for n in tmp_net.hosts]

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='cmd')

    parser_up = subparsers.add_parser('up')
    parser_up.add_argument('host', type=str, choices=hosts)

    parser_genkey = subparsers.add_parser('genkey')
    assert('all' not in hosts) # all is a reserved host name
    parser_genkey.add_argument('host', type=str, choices=['all'] + hosts)

    parser_genclientconf = subparsers.add_parser('gen-client-conf')
    parser_genclientconf.add_argument('host', type=str, choices=hosts)

    args = parser.parse_args()

    if args.cmd == 'up':
        net = gen(tmp_key=False, mock_net=False)
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

    if args.cmd == 'gen-client-conf':
        net = gen(tmp_key=False, mock_net=False)
        e = net.edges[args.host]
        assert(len(e) == 1) # only has one wg conf
        e = e[0]

        wg = None
        for c in net.hosts[args.host].confs.conf:
            if type(c) == Wg:
                wg = c
                break
        assert(wg != None)

        left = net.hosts[args.host]
        right = net.hosts[e[0]]

        print(f"""[Interface]
PrivateKey = {left.key.sk}
Address = {e[1]}/30
DNS = {e[2]}
MTU = 1360

[Peer]
PublicKey = {right.key.pk}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {right.wan_ip}:{wg.port}
PersistentKeepalive = 30
""")