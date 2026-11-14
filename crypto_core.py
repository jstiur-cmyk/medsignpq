"""
crypto_core.py
Inti kriptografi MedSign PQ: tanda tangan digital hibrida ECDSA P-256 + ML-DSA-65.

Alur singkat:
1. Citra dibaca, piksel dinormalkan, lalu di-hash dengan SHA3-256.
2. Hash dan data penandatangan disusun menjadi "payload".
3. Payload ditandatangani dua kali: ECDSA (klasik) dan ML-DSA-65 (pascakuantum).
4. Payload + kedua tanda tangan disisipkan ke metadata PNG (chunk tEXt "medsignpq").
5. Saat verifikasi, citra dinyatakan ASLI hanya jika hash cocok DAN kedua tanda tangan valid.
"""
import base64
import hashlib
import io
import json

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, mldsa
from PIL import Image, PngImagePlugin

META_KEY = "medsignpq"
ALGORITHM = "ECDSA-P256 + ML-DSA-65"
FORMAT_VERSION = 1
SUPPORTED_MODES = ("L", "RGB", "RGBA", "I;16")


# ---------------------------------------------------------------- kunci
def generate_keypairs():
    """Membuat pasangan kunci ECDSA dan ML-DSA untuk satu fasyankes."""
    ec_private = ec.generate_private_key(ec.SECP256R1())
    ml_private = mldsa.MLDSA65PrivateKey.generate()
    return ec_private, ml_private


def private_to_pem(private_key) -> bytes:
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def public_to_pem(public_key) -> str:
    return public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def encrypt_private(private_key, fernet: Fernet) -> str:
    """Kunci privat disimpan dalam keadaan terenkripsi (Fernet)."""
    return fernet.encrypt(private_to_pem(private_key)).decode()


def decrypt_private(token: str, fernet: Fernet):
    return serialization.load_pem_private_key(fernet.decrypt(token.encode()), password=None)


def load_public(pem: str):
    return serialization.load_pem_public_key(pem.encode())


# ---------------------------------------------------------------- citra
def open_image(data: bytes) -> Image.Image:
    """Membuka citra dan menormalkan mode warnanya agar hash selalu konsisten."""
    img = Image.open(io.BytesIO(data))
    img.load()
    if img.mode not in SUPPORTED_MODES:
        has_alpha = img.mode in ("LA", "PA") or (img.mode == "P" and "transparency" in img.info)
        img = img.convert("RGBA" if has_alpha else "RGB")
    return img


def image_hash(img: Image.Image) -> str:
    """SHA3-256 atas mode, ukuran, dan seluruh data piksel (metadata tidak ikut di-hash)."""
    h = hashlib.sha3_256()
    h.update(f"{img.mode}|{img.width}x{img.height}|".encode())
    h.update(img.tobytes())
    return h.hexdigest()


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


# ---------------------------------------------------------------- tanda tangan
def sign_image(img: Image.Image, payload: dict, ec_private, ml_private):
    """Menandatangani citra dan mengembalikan (bytes PNG bertanda tangan, metadata)."""
    payload = dict(payload, v=FORMAT_VERSION, image_hash=image_hash(img))
    message = _canonical(payload)

    sig_ecdsa = ec_private.sign(message, ec.ECDSA(hashes.SHA256()))
    sig_mldsa = ml_private.sign(message)

    meta = {
        "alg": ALGORITHM,
        "payload": payload,
        "sig_ecdsa": base64.b64encode(sig_ecdsa).decode(),
        "sig_mldsa": base64.b64encode(sig_mldsa).decode(),
    }
    info = PngImagePlugin.PngInfo()
    info.add_text(META_KEY, json.dumps(meta))
    info.add_text("Software", "MedSign PQ")

    out = io.BytesIO()
    img.save(out, format="PNG", pnginfo=info)
    return out.getvalue(), meta


def read_signature(img: Image.Image):
    """Mengambil metadata MedSign PQ dari citra. None jika citra belum ditandatangani."""
    raw = getattr(img, "text", {}).get(META_KEY) if hasattr(img, "text") else None
    if raw is None:
        raw = img.info.get(META_KEY)
    if not raw:
        return None
    try:
        meta = json.loads(raw)
        _ = meta["payload"], meta["sig_ecdsa"], meta["sig_mldsa"]
        return meta
    except (ValueError, KeyError, TypeError):
        return None


def verify_image(img: Image.Image, meta: dict, ec_public, ml_public) -> dict:
    """Memeriksa keaslian citra. Hasil: hash_ok, ecdsa_ok, mldsa_ok, valid."""
    payload = meta["payload"]
    message = _canonical(payload)
    hash_ok = image_hash(img) == payload.get("image_hash")

    try:
        ec_public.verify(base64.b64decode(meta["sig_ecdsa"]), message, ec.ECDSA(hashes.SHA256()))
        ecdsa_ok = True
    except (InvalidSignature, ValueError):
        ecdsa_ok = False

    try:
        ml_public.verify(base64.b64decode(meta["sig_mldsa"]), message)
        mldsa_ok = True
    except (InvalidSignature, ValueError):
        mldsa_ok = False

    return {
        "hash_ok": hash_ok,
        "ecdsa_ok": ecdsa_ok,
        "mldsa_ok": mldsa_ok,
        "valid": hash_ok and ecdsa_ok and mldsa_ok,
    }