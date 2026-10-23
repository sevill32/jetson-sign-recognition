# Dataset Rambu Sintetis (Jetson)

Dataset ini dibuat otomatis oleh `tools/make_dataset.py` untuk
pengujian dan pelatihan pengenalan rambu STOP / SLOW / GO.

## Ringkasan

- Kelas: `STOP` (0), `SLOW` (1), `GO` (2), `NONE` (background).
- Split: `train` / `val` / `test`.
- Total gambar: **840**.
- Resolusi: **640x360** piksel.
- Seed: `2026` (hasil deterministik).

| Split | STOP | SLOW | GO | NONE | Total |
|---|---|---|---|---|---|
| train | 168 | 168 | 168 | 84 | 588 |
| val | 36 | 36 | 36 | 18 | 126 |
| test | 36 | 36 | 36 | 18 | 126 |

## Struktur

```
dataset/
├── images/train/*.jpg
├── images/val/*.jpg
├── images/test/*.jpg
├── labels/train/*.txt   # format YOLO
├── labels/val/*.txt
├── labels/test/*.txt
├── labels.csv           # manifest lengkap
├── dataset.yaml        # konfigurasi YOLO
├── classes.txt
└── preview.jpg
```

Format label YOLO: `class_id x_center y_center width height`
(nilai ternormalisasi 0-1). Gambar background memiliki file label
kosong, sehingga bisa dipakai sebagai negative sample.

## Variasi yang dicakup

- Skala sign 0.18-0.62 dari tinggi frame (dekat sampai jauh).
- Rotasi -14 sampai +14 derajat.
- Posisi sign di berbagai area frame.
- Pencahayaan 0.50-1.20 (redup sampai terang).
- Blur ringan pada sebagian sampel.
- Background: gradient, aspal, dinding, langit.

## Regenerasi

```bash
python3 tools/make_dataset.py --per-class 240 --negatives 120 --seed 2026 --overwrite
```

Dataset ini 100% sintetis; tidak memakai foto berhak cipta.
