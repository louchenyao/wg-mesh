import argparse
import os
import signal
import sys
import time

from mesh import Key

key_dir = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "keys"
)

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
        net = gen(tmp_key=False)
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
