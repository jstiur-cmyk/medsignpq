# MedSign PQ — MVP Week 10

Layanan verifikasi integritas citra rontgen berbasis tanda tangan digital hibrida pascakuantum
(ECDSA P-256 + ML-DSA-65). Kelompok 17, D3 Teknologi Informasi, Institut Teknologi Del.

**Anggota:** Maria Christin Gurning (Ketua, 42324058) · Tiur Juliana Sitorus (42324048) · Steven Rizal Simanjuntak (42324031)

## Status Week 10
| Fitur | Status |
|---|---|
| Tampilan utama (beranda) & halaman paket | Sudah terbentuk |
| Daftar & masuk akun fasyankes | Sudah terbentuk |
| Dashboard fasyankes (paket, kuota, riwayat) | Sudah terbentuk |
| Modul tanda tangan hibrida (`crypto_core.py`) | Prototipe, diuji lewat `tests/test_crypto.py` |
| Halaman tanda tangan citra & cek keaslian | Rancangan, diintegrasikan Week 11 |
| Hosting, QR code, pemesanan paket | Rancangan, Week 12 |

## Cara menjalankan
Butuh Python 3.10+ (pustaka `cryptography` versi 46 ke atas sudah mendukung ML-DSA).

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Buka http://127.0.0.1:5000

## Uji modul tanda tangan
```bash
python tests/test_crypto.py
```

## Struktur
