"""
app.py
Aplikasi web MedSign PQ (MVP versi 1).
Jalankan:  python app.py   lalu buka http://127.0.0.1:5000
"""
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from cryptography.fernet import Fernet
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_file, session, url_for)
from PIL import UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash

import crypto_core as cc

BASE_DIR = Path(__file__).resolve().parent
INSTANCE = Path(os.environ.get("MEDSIGN_INSTANCE", BASE_DIR / "instance"))
SIGNED_DIR = INSTANCE / "signed"
DB_PATH = INSTANCE / "medsignpq.db"
ALLOWED_EXT = {"png", "jpg", "jpeg"}

PLANS = {
    "uji_coba": {"nama": "Uji Coba", "kuota": 300, "harga": "Gratis", "durasi_hari": 90},
    "klinik": {"nama": "Klinik", "kuota": 500, "harga": "Rp350.000/bulan", "durasi_hari": 30},
    "rumah_sakit": {"nama": "Rumah Sakit", "kuota": 2000, "harga": "Rp750.000/bulan", "durasi_hari": 30},
}
ORG_TYPES = ["Rumah Sakit", "Klinik Radiologi", "Laboratorium Radiologi", "Lainnya"]

app = Flask(__name__, instance_path=str(INSTANCE))
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB


# ------------------------------------------------------------------ setup
def _load_or_create(path: Path, make) -> bytes:
    if not path.exists():
        path.write_bytes(make())
    return path.read_bytes()


INSTANCE.mkdir(exist_ok=True)
SIGNED_DIR.mkdir(exist_ok=True)
app.secret_key = os.environ.get("SECRET_KEY") or _load_or_create(
    INSTANCE / "flask.key", lambda: secrets.token_hex(32).encode()).decode()
FERNET = Fernet(os.environ.get("KEY_ENCRYPTION_KEY") or _load_or_create(
    INSTANCE / "kek.key", Fernet.generate_key))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_name TEXT NOT NULL,
    org_type TEXT NOT NULL,
    pic_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    password_hash TEXT NOT NULL,
    ec_public TEXT NOT NULL,
    ml_public TEXT NOT NULL,
    ec_private_enc TEXT NOT NULL,
    ml_private_enc TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'uji_coba',
    plan_until TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signatures (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    filename TEXT NOT NULL,
    description TEXT,
    image_hash TEXT NOT NULL,
    width INTEGER, height INTEGER,
    signed_at TEXT NOT NULL,
    file_path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signature_id TEXT,
    result TEXT NOT NULL,
    checked_at TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


with sqlite3.connect(DB_PATH) as _conn:
    _conn.executescript(SCHEMA)


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@app.template_filter("tgl")
def format_tanggal(value):
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return value
    bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{dt.day} {bulan[dt.month - 1]} {dt.year}, {dt:%H:%M} WIB"


# ------------------------------------------------------------------ auth
def current_user():
    uid = session.get("uid")
    if uid is None:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


@app.context_processor
def inject_user():
    return {"user": current_user(), "PLANS": PLANS}


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            flash("Silakan masuk terlebih dahulu.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def quota_used(user_id):
    month = datetime.now().strftime("%Y-%m")
    row = get_db().execute(
        "SELECT COUNT(*) AS n FROM signatures WHERE user_id = ? AND substr(signed_at,1,7) = ?",
        (user_id, month)).fetchone()
    return row["n"]


# ------------------------------------------------------------------ halaman publik
@app.route("/")
def index():
    db = get_db()
    stats = {
        "fasyankes": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "citra": db.execute("SELECT COUNT(*) FROM signatures").fetchone()[0],
        "cek": db.execute("SELECT COUNT(*) FROM verifications").fetchone()[0],
    }
    return render_template("index.html", stats=stats)


@app.route("/paket")
def paket():
    return render_template("paket.html")


@app.route("/daftar", methods=["GET", "POST"])
def register():
    form = request.form
    if request.method == "POST":
        org_name = form.get("org_name", "").strip()
        org_type = form.get("org_type", "")
        pic_name = form.get("pic_name", "").strip()
        email = form.get("email", "").strip().lower()
        phone = form.get("phone", "").strip()
        password = form.get("password", "")
        confirm = form.get("confirm", "")

        errors = []
        if len(org_name) < 3:
            errors.append("Nama fasyankes minimal 3 karakter.")
        if org_type not in ORG_TYPES:
            errors.append("Pilih jenis fasyankes.")
        if len(pic_name) < 3:
            errors.append("Nama penanggung jawab minimal 3 karakter.")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Format email tidak valid.")
        if len(password) < 8:
            errors.append("Kata sandi minimal 8 karakter.")
        if password != confirm:
            errors.append("Konfirmasi kata sandi tidak sama.")
        db = get_db()
        if not errors and db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            errors.append("Email sudah terdaftar. Silakan masuk.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=form, org_types=ORG_TYPES)

        ec_priv, ml_priv = cc.generate_keypairs()
        plan_until = (datetime.now() + timedelta(days=PLANS["uji_coba"]["durasi_hari"])).strftime("%Y-%m-%d %H:%M:%S")
        cur = db.execute(
            """INSERT INTO users (org_name, org_type, pic_name, email, phone, password_hash,
               ec_public, ml_public, ec_private_enc, ml_private_enc, plan, plan_until, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (org_name, org_type, pic_name, email, phone, generate_password_hash(password),
             cc.public_to_pem(ec_priv.public_key()), cc.public_to_pem(ml_priv.public_key()),
             cc.encrypt_private(ec_priv, FERNET), cc.encrypt_private(ml_priv, FERNET),
             "uji_coba", plan_until, now_iso()))
        db.commit()
        session.clear()
        session["uid"] = cur.lastrowid
        flash("Akun berhasil dibuat. Kunci tanda tangan hibrida fasyankes Anda sudah disiapkan.", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html", form=form, org_types=ORG_TYPES)


@app.route("/masuk", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        row = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            flash("Email atau kata sandi salah.", "error")
            return render_template("login.html", email=email)
        session.clear()
        session["uid"] = row["id"]
        nxt = request.args.get("next", "")
        return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
    return render_template("login.html", email="")


@app.route("/keluar")
def logout():
    session.clear()
    flash("Anda sudah keluar.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------------ fasyankes
@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    rows = get_db().execute(
        """SELECT s.*, (SELECT COUNT(*) FROM verifications v WHERE v.signature_id = s.id) AS n_cek
           FROM signatures s WHERE user_id = ? ORDER BY signed_at DESC""", (user["id"],)).fetchall()
    plan = PLANS[user["plan"]]
    used = quota_used(user["id"])
    return render_template("dashboard.html", rows=rows, plan=plan, used=used,
                           remaining=max(plan["kuota"] - used, 0))


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


@app.route("/tandatangani", methods=["GET", "POST"])
@login_required
def sign():
    user = current_user()
    plan = PLANS[user["plan"]]
    used = quota_used(user["id"])
    if request.method == "POST":
        file = request.files.get("image")
        description = request.form.get("description", "").strip()[:120]
        if file is None or file.filename == "":
            flash("Pilih file citra rontgen terlebih dahulu.", "error")
            return redirect(url_for("sign"))
        if not _allowed(file.filename):
            flash("Format file harus PNG atau JPG.", "error")
            return redirect(url_for("sign"))
        if used >= plan["kuota"]:
            flash("Kuota paket bulan ini sudah habis. Silakan tingkatkan paket.", "error")
            return redirect(url_for("paket"))
        if datetime.now().strftime("%Y-%m-%d %H:%M:%S") > user["plan_until"]:
            flash("Masa aktif paket Anda sudah berakhir.", "error")
            return redirect(url_for("paket"))
        try:
            img = cc.open_image(file.read())
        except (UnidentifiedImageError, OSError):
            flash("File tidak dapat dibaca sebagai citra. Pastikan file PNG/JPG tidak rusak.", "error")
            return redirect(url_for("sign"))

        existing = cc.read_signature(img)
        if existing is not None:
            flash("Citra ini sudah memiliki tanda tangan MedSign PQ (ID "
                  f"{existing['payload'].get('sid', '-')}). Gunakan citra asli yang belum ditandatangani.", "error")
            return redirect(url_for("sign"))

        sid = "MSPQ-" + secrets.token_hex(4).upper()
        signed_at = now_iso()
        payload = {
            "sid": sid,
            "signer_id": user["id"],
            "signer_name": user["org_name"],
            "signed_at": signed_at,
        }
        ec_priv = cc.decrypt_private(user["ec_private_enc"], FERNET)
        ml_priv = cc.decrypt_private(user["ml_private_enc"], FERNET)
        png_bytes, meta = cc.sign_image(img, payload, ec_priv, ml_priv)

        base = Path(file.filename).stem[:60] or "citra"
        out_name = f"{base}_signed.png"
        path = SIGNED_DIR / f"{sid}.png"
        path.write_bytes(png_bytes)
        db = get_db()
        db.execute(
            """INSERT INTO signatures (id, user_id, filename, description, image_hash, width, height, signed_at, file_path)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (sid, user["id"], out_name, description, meta["payload"]["image_hash"],
             img.width, img.height, signed_at, str(path)))
        db.commit()
        flash("Citra berhasil ditandatangani dengan tanda tangan hibrida.", "success")
        return redirect(url_for("sign_result", sid=sid))
    return render_template("sign.html", plan=plan, used=used, remaining=max(plan["kuota"] - used, 0))


def _own_signature(sid):
    row = get_db().execute("SELECT * FROM signatures WHERE id = ?", (sid,)).fetchone()
    if row is None or row["user_id"] != current_user()["id"]:
        abort(404)
    return row


@app.route("/tandatangani/<sid>")
@login_required
def sign_result(sid):
    row = _own_signature(sid)
    return render_template("sign_result.html", row=row,
                           check_url=url_for("check_record", sid=sid, _external=True))


@app.route("/unduh/<sid>")
@login_required
def download(sid):
    row = _own_signature(sid)
    return send_file(row["file_path"], mimetype="image/png", as_attachment=True, download_name=row["filename"])


# ------------------------------------------------------------------ verifikasi publik
def _log_check(sid, result):
    db = get_db()
    db.execute("INSERT INTO verifications (signature_id, result, checked_at) VALUES (?,?,?)",
               (sid, result, now_iso()))
    db.commit()


@app.route("/cek", methods=["GET", "POST"])
def check():
    if request.method == "GET":
        return render_template("check.html")

    file = request.files.get("image")
    if file is None or file.filename == "":
        flash("Pilih file citra yang ingin dicek.", "error")
        return redirect(url_for("check"))
    try:
        img = cc.open_image(file.read())
    except (UnidentifiedImageError, OSError):
        flash("File tidak dapat dibaca sebagai citra.", "error")
        return redirect(url_for("check"))

    meta = cc.read_signature(img)
    if meta is None:
        _log_check(None, "tidak_bertanda_tangan")
        return render_template("check_result.html", status="unsigned", filename=file.filename)

    payload = meta["payload"]
    db = get_db()
    signer = db.execute("SELECT * FROM users WHERE id = ?", (payload.get("signer_id"),)).fetchone()
    record = db.execute("SELECT * FROM signatures WHERE id = ?", (payload.get("sid"),)).fetchone()
    if signer is None or record is None:
        _log_check(payload.get("sid"), "tidak_terdaftar")
        return render_template("check_result.html", status="unknown", payload=payload, filename=file.filename)

    result = cc.verify_image(img, meta, cc.load_public(signer["ec_public"]), cc.load_public(signer["ml_public"]))
    if result["valid"]:
        status = "valid"
    elif not result["hash_ok"] and result["ecdsa_ok"] and result["mldsa_ok"]:
        status = "modified"
    else:
        status = "invalid"
    _log_check(payload["sid"], status)
    return render_template("check_result.html", status=status, result=result, payload=payload,
                           signer=signer, record=record, filename=file.filename)


@app.route("/cek/<sid>")
def check_record(sid):
    db = get_db()
    record = db.execute(
        """SELECT s.*, u.org_name, u.org_type FROM signatures s JOIN users u ON u.id = s.user_id
           WHERE s.id = ?""", (sid,)).fetchone()
    return render_template("check_record.html", record=record, sid=sid)


@app.errorhandler(413)
def too_large(_e):
    flash("Ukuran file melebihi 20 MB.", "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)