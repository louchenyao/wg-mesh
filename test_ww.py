from ww import Key, Link

import os
import tempfile


def test_Key():
    with tempfile.TemporaryDirectory() as tmp_dir:
        p = os.path.join(tmp_dir, "tmp.key")

        # new the key
        k = Key(None)
        pk = k.pk
        sk = k.sk
        k.dump(p)
        del k

        # reload teh ky
        k1 = Key(p)
        assert(k1.pk == pk)
        assert(k1.sk == sk)


def test_Link_real():
    # generate confs
    left_key = Key(None)
    right_key = Key(None)
    link = Link(left_key, right_key, right_wan_ip="10.1.1.1",
                link_cidr="192.168.1.8", port="1234", mtu=1420)
    left_conf = link.generate_left_config(None)
    right_conf = link.generate_right_config()

    with open("right.conf", "w") as f:
        f.write(right_conf)

    with open("left.conf", "w") as f:
        f.write(left_conf)

    # setup two namespaces
    assert(os.system("sudo ip netns del left"))
    assert(os.system("sudo ip netns del right"))
    assert(os.system("sudo ip netns add left") == 0)
    assert(os.system("sudo ip netns add right") == 0)
    # config left ns
    assert(os.system(
        "sudo ip netns exec left    ip link add left-dev type veth peer name right-dev") == 0)
    assert(os.system("sudo ip netns exec left    ip link set right-dev netns right") == 0)
    assert(os.system("sudo ip netns exec left    ip link set left-dev up") == 0)
    assert(os.system(
        "sudo ip netns exec left    ip addr add 10.1.1.2/24 dev left-dev") == 0)
    # config right ns
    assert(os.system("sudo ip netns exec right    ip link set right-dev up") == 0)
    assert(os.system(
        "sudo ip netns exec right    ip addr add 10.1.1.1/24 dev right-dev") == 0)

    # up wg
    assert(os.system("sudo ip netns exec right    wg-quick up ./right.conf") == 0)
    assert(os.system("sudo ip netns exec left    wg-quick up ./left.conf") == 0)

    # ping
    assert(os.system("sudo ip netns exec left ping 192.168.1.10 -c 4") == 0)

    # teardown
    assert(os.system("rm left.conf right.conf") == 0)
    assert(os.system("sudo ip netns del left") == 0)
    assert(os.system("sudo ip netns del right") == 0)