from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

STATIC = Path(__file__).resolve().parent / "static"
STATIC.mkdir(exist_ok=True)

NAVY = (10, 31, 61)
NAVY2 = (20, 59, 114)
TEAL = (32, 187, 176)
GREEN = (61, 220, 151)
WHITE = (255, 255, 255)


def font(size):
    for name in ("segoeuib.ttf", "arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
                 "C:/Windows/Fonts/arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def gambar_ikon(s=512):
    S = s * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top, left, right, bottom = S * 0.06, S * 0.12, S * 0.88, S * 0.96
    mid = S / 2
    perisai = [(mid, top), (right, top + S * 0.10), (right, S * 0.50),
               (mid + S * 0.30, S * 0.80), (mid, bottom),
               (mid - S * 0.30, S * 0.80), (left, S * 0.50), (left, top + S * 0.10)]
    d.polygon(perisai, fill=NAVY)
    dalam = [(x + (mid - x) * 0.08, y + (S * 0.5 - y) * 0.08) for x, y in perisai]
    d.line(dalam + [dalam[0]], fill=NAVY2, width=int(S * 0.012))

    w, L = S * 0.16, S * 0.46
    cx, cy = mid, S * 0.47
    r = int(S * 0.03)
    d.rounded_rectangle((cx - w / 2, cy - L / 2, cx + w / 2, cy + L / 2), radius=r, fill=TEAL)
    d.rounded_rectangle((cx - L / 2, cy - w / 2, cx + L / 2, cy + w / 2), radius=r, fill=TEAL)

    for i in range(-2, 3):
        for j in range(-2, 3):
            x, y = cx + i * S * 0.045, cy + j * S * 0.045
            if abs(x - cx) <= w / 2 or abs(y - cy) <= w / 2:
                d.ellipse((x - S * 0.008, y - S * 0.008, x + S * 0.008, y + S * 0.008), fill=WHITE)

    centang = [(S * 0.30, S * 0.55), (S * 0.44, S * 0.69), (S * 0.74, S * 0.33)]
    d.line(centang, fill=NAVY, width=int(S * 0.11), joint="curve")
    d.line(centang, fill=GREEN, width=int(S * 0.07), joint="curve")
    return img.resize((s, s), Image.LANCZOS)


def gambar_logo():
    ikon = gambar_ikon(220)
    W, H = 1400, 240
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.paste(ikon, (6, 10), ikon)
    d = ImageDraw.Draw(img)
    f_besar = font(92)
    d.text((240, 34), "MedSign", font=f_besar, fill=NAVY)
    lebar = d.textbbox((240, 34), "MedSign", font=f_besar)[2]
    f_pq = font(56)
    x0 = lebar + 18
    kotak = d.textbbox((0, 0), "PQ", font=f_pq)
    bw, bh = kotak[2] - kotak[0] + 34, 84
    d.rounded_rectangle((x0, 46, x0 + bw, 46 + bh), radius=18, fill=TEAL)
    d.text((x0 + 17 - kotak[0], 46 + (bh - (kotak[3] - kotak[1])) / 2 - kotak[1]), "PQ", font=f_pq, fill=WHITE)
    d.text((244, 156), "Citra Medis Asli, Aman hingga Era Kuantum", font=font(30), fill=NAVY2)
    return img.crop(img.getbbox())


ikon = gambar_ikon(512)
ikon.resize((256, 256), Image.LANCZOS).save(STATIC / "icon.png")
ikon.resize((64, 64), Image.LANCZOS).save(STATIC / "favicon.png")
gambar_logo().save(STATIC / "logo.png")
print("Selesai! Logo tersimpan di folder static: logo.png, icon.png, favicon.png")