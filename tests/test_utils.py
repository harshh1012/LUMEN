from src.utils import ensure_dir
import tempfile, os

def test_ensure_dir():
    tmp_dir = tempfile.mkdtemp()
    new_dir = os.path.join(tmp_dir, "demo")
    ensure_dir(new_dir)
    assert os.path.exists(new_dir)
