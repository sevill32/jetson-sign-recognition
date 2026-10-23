# Prosedur dan Hasil Pengujian

## 1. Tujuan

Memverifikasi bahwa sistem:

1. Mengenali minimal 3 sign (STOP, SLOW, GO) pada minimal **3 jarak**.
2. Bekerja pada minimal **2 kondisi pencahayaan**.
3. Mengubah LED sesuai sign yang dikenali.
4. Menangani **pergantian sign** dan **kondisi tidak ada sign** dengan benar
   (masuk safe state).
5. Menampilkan sign, confidence, dan status LED.

## 2. Peralatan

- Jetson Nano + kamera CSI + 3 LED + resistor (sudah di-wiring).
- Sign STOP, SLOW, GO yang dicetak (lebar minimal 15 cm) dan ditempel karton.
- Penggaris/meteran.
- Sumber cahaya tambahan (lampu meja) untuk kondisi redup/terang.
- Monitor/SSH untuk melihat log dan menyimpan screenshot.

## 3. Matriks Minimum

| Faktor | Nilai |
|---|---|
| Sign | STOP, SLOW, GO |
| Jarak | 0.3 m, 0.6 m, 1 m |
| Pencahayaan | terang (lampu ruangan + lampu meja) dan redup (lampu ruangan saja / intensitas diturunkan) |
| Jumlah kondisi | 3 x 3 x 2 = **18 kondisi** |
| Durasi per kondisi | minimal 4 detik / 60 frame |

Tambahan wajib:

- Uji transisi: STOP -> SLOW -> GO -> tanpa sign.
- Uji tanpa sign (safe state).
- Uji confidence di bawah threshold (opsional: naikkan threshold ke 0.95
  sehingga sign valid pun dianggap low confidence).

## 4. Prosedur

### 4.1 Persiapan

```bash
cd jetson-sign-recognition

# pastikan kamera dan LED bekerja
python3 main.py --headless --duration 5
python3 tools/test_leds.py
```

Atur kamera pada ketinggian yang sama dengan sign, menghadap lurus.
Gunakan latar belakang polos (dinding) agar sign mudah terlihat.

### 4.2 Evaluasi otomatis 18 kondisi

```bash
python3 tools/evaluate_camera.py --all --seconds 4
```

Alur:

1. Program meminta Anda memposisikan sign sesuai kondisi.
2. Tekan Enter; program merekam selama 4 detik.
3. Program menghitung akurasi deteksi dan menyimpan screenshot
   beranotasi.
4. Ulangi untuk 18 kondisi.

Hasil:

- `results/evaluation_camera.csv`
- `results/screenshots/real_<SIGN>_<jarak>_<cahaya>.jpg`

> `evaluate_camera.py` hanya mengukur akurasi deteksi dan tidak
> mengendalikan GPIO. Untuk mengisi kolom **LED benar?**, jalankan
> `python3 main.py` pada kondisi yang sama dan amati LED.

### 4.3 Evaluasi satu kondisi

```bash
python3 tools/evaluate_camera.py --sign STOP --distance 1.0m \
    --lighting terang --seconds 4
```

### 4.4 Uji transisi sign

1. Jalankan `python3 main.py`.
2. Tampilkan STOP di depan kamera selama ~2 detik.
3. Ganti ke SLOW, lalu GO, lalu hilangkan sign.
4. Amati LED:
   - STOP -> hanya LED merah ON.
   - SLOW -> hanya LED kuning ON.
   - GO -> hanya LED hijau ON.
   - tanpa sign -> semua LED OFF (setelah ~8 frame).
5. Catat screenshot untuk setiap state (otomatis disimpan pada perubahan
   state di `results/runtime/snapshots/`).

### 4.5 Uji safe state / low confidence

- **Tanpa sign:** arahkan kamera ke dinding kosong, pastikan semua LED OFF
  dan status `SAFE=yes`.
- **Low confidence:** jalankan `python3 main.py --threshold 0.95`; sign yang
  biasanya terdeteksi sekarang harus ditolak dan sistem tetap SAFE.

## 5. Hasil Pengujian Otomatis (Software)

### 5.1 Unit test

```
Ran 18 tests in ~4.7s
OK
```

### 5.2 Synthetic benchmark

3 sign x 3 jarak x 2 pencahayaan x 3 variasi = 54 frame:

| Pencahayaan | Jarak | STOP | SLOW | GO |
|---|---|---|---|---|
| terang | dekat | 3/3 | 3/3 | 3/3 |
| terang | sedang | 3/3 | 3/3 | 3/3 |
| terang | jauh | 3/3 | 3/3 | 3/3 |
| redup | dekat | 3/3 | 3/3 | 3/3 |
| redup | sedang | 3/3 | 3/3 | 3/3 |
| redup | jauh | 3/3 | 3/3 | 3/3 |

**Total: 54/54 (100%). False positive tanpa sign: 0/10.**
Detail mean confidence: `results/synthetic/summary.md`.

### 5.3 Demo alur keputusan

Video `results/demo/demo_signs.mp4` (STOP -> SLOW -> GO -> tanpa sign -> STOP
-> tanpa sign):

- 217 frame, 19.6 FPS.
- SAFE=48, STOP=83, SLOW=53, GO=33.
- Transisi LED benar pada setiap perubahan sign.
- Log: `results/demo_run.log`.

### 5.4 Integrasi kamera nyata

- 10 detik, 173 frame, 17.2 FPS.
- Semua SAFE (tidak ada sign di depan kamera).
- Tidak ada false positive setelah filter geometri.
- Snapshot: `results/screenshots/camera_safe_state.jpg`.

> Catatan: pengujian ini membuktikan pipeline kamera -> deteksi -> decision ->
> safe state. Pengujian LED fisik dan matriks sign fisik harus diisi pada
> tabel berikut setelah hardware siap.

## 6. Tabel Isian Pengujian Fisik

Isi setelah menjalankan `tools/evaluate_camera.py --all`.

| No | Sign | Jarak | Cahaya | FPS | Benar | Confidence | LED benar? | Screenshot |
|---|---|---|---|---|---|---|---|---
| 1 | STOP | 0.3 m | terang | 11.9 | ✓ | 1.00 | ✓ | ✓ |
| 2 | SLOW | 0.3 m | terang | 10.3 | ✓ | 0.81 | ✓ | ✓ |
| 3 | GO | 0.3 m | terang | 10.6 | ✓ | 1.00 | ✓ | ✓ |
| 4 | STOP | 0.6 m | terang | 14.3 | ✓ | 0.93 | ✓ | ✓ |
| 5 | SLOW | 0.6 m | terang | 10.2 | ✓ | 0.72 | ✓ | ✓ |
| 6 | GO | 0.6 m | terang | 10.4 | ✓ | 0.95 | ✓ | ✓ |
| 7 | STOP | 1 m | terang | 12.6 | ✓ | 0.93 | ✓ | ✓ |
| 8 | SLOW | 1 m | terang | 10.4 | ✓ | 0.69 | ✓ | ✓ |
| 9 | GO | 1 m | terang | 11.2 | ✓ | 0.90 | ✓ | ✓ |
| 10 | STOP | 0.3 m | redup | 10.0 | ✓ | 1.00 | ✓ | ✓ |
| 11 | SLOW | 0.3 m | redup | 9.9 | ✓ | 0.81 | ✓ | ✓ |
| 12 | GO | 0.3 m | redup |  10.2 | ✓ | 1.00 | ✓ | ✓ |
| 13 | STOP | 0.6 m | redup | 10.0 | ✓ | 1.00 | ✓ | ✓ |
| 14 | SLOW | 0.6 m | redup | 10.0 | ✓ | 0.77 | ✓ | ✓ |
| 15 | GO | 0.6 m | redup | 9.6 | ✓ | 0.99 | ✓ | ✓ |
| 16 | STOP | 1 m | redup | 10.4 | ✓ | 0.93 | ✓ | ✓ |
| 17 | SLOW | 1 m | redup | 10.1 | ✓ | 0.69 | ✓ | ✓ |
| 18 | GO | 1 m | redup | 10.3 | ✓ | 0.91 | ✓ | ✓ |

## 7. Checklist Verifikasi LED

| Uji | Kriteria lulus | Hasil |
|---|---|---|
| STOP terdeteksi | hanya LED merah ON, dua lainnya OFF | |
| SLOW terdeteksi | hanya LED kuning ON | |
| GO terdeteksi | hanya LED hijau ON | |
| Tanpa sign | semua LED OFF, status SAFE | |
| Confidence < threshold | semua LED OFF, status SAFE | |
| Transisi STOP -> SLOW | LED merah OFF, kuning ON | |
| Transisi SLOW -> GO | LED kuning OFF, hijau ON | |
| Sign dihilangkan | LED terakhir OFF setelah ~8 frame | |
| Program dihentikan | semua LED OFF | |

## 8. Kriteria Kelulusan

- Minimal 3 sign dikenali dengan benar.
- Akurasi >= 80% pada setiap kondisi (disarankan 100% untuk kondisi
  terkontrol).
- Tidak ada false positive pada kondisi tanpa sign.
- LED berubah sesuai mapping pada setiap sign.
- Safe state tercapai saat tidak ada sign / confidence rendah.
- Pergantian sign tertangani tanpa LED nyangkut di state lama.
