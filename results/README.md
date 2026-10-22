# Hasil Pengujian

Ringkasan bukti pengujian yang sudah dijalankan pada Jetson Nano
(L4T R32.6.1, OpenCV 3.2.0, Python 3.6.9).

## 1. Unit Test

```
Ran 18 tests
OK
```

- Detector: 7 test (3 sign, cahaya redup, jarak jauh, frame kosong,
  pemetaan bbox, serialisasi).
- Decision logic: 6 test (threshold, debounce, transisi, safe state).
- GPIO simulasi: 5 test (mapping, all-off, blink, status).

## 2. Synthetic Benchmark

54 frame (3 sign x 3 jarak x 2 pencahayaan x 3 variasi) + 10 frame kosong.

| Pencahayaan | Jarak | STOP | SLOW | GO | Mean confidence |
|---|---|---|---|---|---|
| terang | dekat | 100% | 100% | 100% | 0.95-1.00 |
| terang | sedang | 100% | 100% | 100% | 0.94-1.00 |
| terang | jauh | 100% | 100% | 100% | 0.87-0.95 |
| redup | dekat | 100% | 100% | 100% | 0.95-1.00 |
| redup | sedang | 100% | 100% | 100% | 0.93-1.00 |
| redup | jauh | 100% | 100% | 100% | 0.86-0.95 |

- **Akurasi total: 100% (54/54).**
- **False positive tanpa sign: 0/10.**
- Tabel lengkap: [`synthetic/summary.md`](synthetic/summary.md).
- CSV: [`synthetic/benchmark.csv`](synthetic/benchmark.csv).
- Screenshot beranotasi: [`synthetic/terang/`](synthetic/terang/) dan
  [`synthetic/redup/`](synthetic/redup/).

## 3. Demo Alur Keputusan dan Pergantian Sign

Video: [`demo/demo_signs.mp4`](demo/demo_signs.mp4)
(160 frame @ 20 fps: STOP -> SLOW -> GO -> tanpa sign -> STOP -> tanpa sign).

Eksekusi `main.py --camera video --simulate-gpio --duration 11`:

- 217 frame, 19.6 FPS rata-rata.
- SAFE=48, STOP=83, SLOW=53, GO=33.
- Perubahan LED simulasi sesuai sign.
- Kembali ke SAFE saat sign dihilangkan.
- Log lengkap: [`demo_run.log`](demo_run.log).

## 4. Integrasi Kamera CSI Nyata

- Kamera: IMX219 sensor-id 0, output 640x360, flip `rotate180`.
- Durasi 10 detik, 173 frame, 17.2 FPS.
- Tidak ada sign di depan kamera -> semua SAFE, tidak ada false positive.
- Snapshot: [`screenshots/camera_safe_state.jpg`](screenshots/camera_safe_state.jpg).

## 5. Bukti Screenshot

| State | File |
|---|---|
| STOP | [`screenshots/demo_STOP.jpg`](screenshots/demo_STOP.jpg) |
| SLOW | [`screenshots/demo_SLOW.jpg`](screenshots/demo_SLOW.jpg) |
| GO | [`screenshots/demo_GO.jpg`](screenshots/demo_GO.jpg) |
| SAFE | [`screenshots/demo_SAFE.jpg`](screenshots/demo_SAFE.jpg) |
| Kamera nyata (safe) | [`screenshots/camera_safe_state.jpg`](screenshots/camera_safe_state.jpg) |
| Synthetic STOP | [`screenshots/synthetic_STOP_dekat.jpg`](screenshots/synthetic_STOP_dekat.jpg) |
| Synthetic SLOW | [`screenshots/synthetic_SLOW_sedang.jpg`](screenshots/synthetic_SLOW_sedang.jpg) |
| Synthetic GO redup | [`screenshots/synthetic_GO_jauh_redup.jpg`](screenshots/synthetic_GO_jauh_redup.jpg) |

## 6. Pengujian Fisik (Menunggu Hardware)

Yang masih perlu dilakukan dengan sign cetak + LED asli:

- [ ] Matriks 3 sign x 3 jarak x 2 pencahayaan (18 kondisi).
- [ ] Verifikasi LED merah/kuning/hijau menyala sesuai sign.
- [ ] Uji transisi STOP -> SLOW -> GO -> tanpa sign.
- [ ] Uji safe state saat tidak ada sign.
- [ ] Uji confidence di bawah threshold.
- [ ] Foto sistem lengkap (Jetson + kamera + LED + sign).

Gunakan:

```bash
python3 tools/test_leds.py
python3 tools/evaluate_camera.py --all --seconds 4
```

Hasil akan masuk ke `evaluation_camera.csv` dan
`screenshots/real_*.jpg`. Prosedur: [`../docs/testing.md`](../docs/testing.md).

## 7. Cara Reproduksi

```bash
python3 -m unittest discover -s tests -v
python3 tools/synthetic_benchmark.py
python3 tools/make_demo_video.py
python3 main.py --camera video --video results/demo/demo_signs.mp4 \
                --headless --simulate-gpio --duration 11
```
