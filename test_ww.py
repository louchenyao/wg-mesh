from ww import Key

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