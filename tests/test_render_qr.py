"""T10：QR helper 行为验收（RFC §3.8）。干净 venv 变体由 CI 单独 job 覆盖。"""
import shutil
import subprocess
import sys
from pathlib import Path

QR = Path(__file__).resolve().parents[1] / "skills/ai_customer_design/scripts/render_qr.py"

def run_qr(*args):
    return subprocess.run([sys.executable, str(QR), *args],
                          capture_output=True, text=True)

def test_normal_url_generates_decodable_png(tmp_path):
    out = tmp_path / "qr.png"
    r = run_qr("https://example.com/p/123", "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert out.exists() and out.stat().st_size > 0
    try:
        from PIL import Image  # 可选：装了 pyzbar 就解码验证
        import pyzbar.pyzbar as pyzbar
        decoded = pyzbar.decode(Image.open(out))
        assert any(b"https://example.com/p/123" in d.data for d in decoded)
    except ImportError:
        pass  # 解码器不可用时仅验证文件生成

def test_empty_url_fails_with_user_error():
    r = run_qr("")
    assert r.returncode != 0
    assert "E-USER-" in r.stderr

def test_unwritable_out_dir_fails():
    r = run_qr("https://example.com/p/1", "--out", "/proc/x/qr.png")
    assert r.returncode != 0
    assert "E-USER-" in r.stderr

def test_missing_dependency_prints_link(tmp_path, monkeypatch):
    # 模拟 vendor 不可达：把 vendor 目录改名
    vendor = QR.parent.parent / "vendor"
    renamed = tmp_path / "vendor-moved"
    shutil.move(str(vendor), str(renamed))
    try:
        r = run_qr("https://example.com/p/1")
        assert r.returncode != 0
        assert "https://example.com/p/1" in r.stdout  # 链接回退到 stdout
    finally:
        shutil.move(str(renamed), str(vendor))
