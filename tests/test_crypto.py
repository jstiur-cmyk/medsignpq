"""
test_crypto.py
Uji inti tanda tangan hibrida MedSign PQ:
1. citra asli harus terbaca ASLI
2. citra yang diubah 1 piksel harus terbaca TIDAK ASLI
"""
import sys
from pathlib import Path

# supaya file crypto_core.py di folder utama bisa di-import
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import crypto_core as cc

CITRA = ROOT / "citra_uji_sintetis_1.png"
HASIL = ROOT / "citra_ditandatangani.png"


def status(hasil):
    return "ASLI" if hasil["valid"] else "TIDAK ASLI"


# 1. buat pasangan kunci ECDSA + ML-DSA
ec_priv, ml_priv = cc.generate_keypairs()
print("1. Kunci ECDSA P-256 dan ML-DSA-65 berhasil dibuat")

# 2. buka citra dan tandatangani
img = cc.open_image(CITRA.read_bytes())
payload = {
    "sid": "MSPQ-TEST0001",
    "signer_id": 1,
    "signer_name": "Klinik Uji Internal Kelompok 17",
    "signed_at": "2026-11-13 10:00:00",
}
png_bytes, meta = cc.sign_image(img, payload, ec_priv, ml_priv)
HASIL.write_bytes(png_bytes)
print("2. Citra ditandatangani, disimpan sebagai", HASIL.name)
print("   Hash SHA3-256 :", meta["payload"]["image_hash"][:32], "...")

# 3. verifikasi citra asli
signed = cc.open_image(png_bytes)
meta_dibaca = cc.read_signature(signed)
hasil = cc.verify_image(signed, meta_dibaca, ec_priv.public_key(), ml_priv.public_key())
print("3. Cek citra asli   ->", status(hasil), hasil)

# 4. ubah 1 piksel lalu verifikasi lagi
px = signed.load()
px[100, 100] = (px[100, 100] + 1) % 256
hasil = cc.verify_image(signed, meta_dibaca, ec_priv.public_key(), ml_priv.public_key())
print("4. Cek citra diubah ->", status(hasil), hasil)