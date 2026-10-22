# Arsitektur Sistem

![Arsitektur](architecture.png)

Diagram vektor: [`architecture.svg`](architecture.svg) |
sumber Graphviz: [`architecture.dot`](architecture.dot)

## 1. Alur Data

```
┌──────────────┐   BGR frame    ┌────────────────────┐
│ Kamera CSI   │ ─────────────> │ GStreamer/Argus    │
│ IMX219       │                │ nvarguscamerasrc   │
└──────────────┘                │ -> nvvidconv      │
                                │ -> appsink        │
                                └─────────┬──────────┘
                                          │ 640x360 BGR
                                          v
                                ┌────────────────────┐
                                │ Preprocessing      │
                                │ resize, blur, HSV  │
                                └─────────┬──────────┘
                                          v
                                ┌────────────────────┐
                                │ Color segmentation │
                                │ merah/kuning/hijau │
                                │ + morphology       │
                                └─────────┬──────────┘
                                          v
                                ┌────────────────────┐
                                │ Shape analysis     │
                                │ contour, hull,     │
                                │ approxPolyDP       │
                                └─────────┬──────────┘
                                          v
                                ┌────────────────────┐
                                │ Confidence score   │
                                │ 0.55S + 0.30C      │
                                │ + 0.15A            │
                                └─────────┬──────────┘
                                          v
                                ┌────────────────────┐
                                │ Decision logic     │
                                │ threshold, debounce│
                                │ safe state         │
                                └──────┬───────┬─────┘
                                       │       │
                              sign     │       │ no sign / low conf
                                       v       v
                                ┌──────────┐ ┌───────────┐
                                │ GPIO LED │ │ Safe state│
                                └──────────┘ └───────────┘
                                       │
                                       v
                                ┌────────────────────┐
                                │ Overlay + CSV log  │
                                │ + snapshot         │
                                └────────────────────┘
```

## 2. Modul dan Interface

### `signrec/camera.py`

| Class/function | Deskripsi |
|---|---|
| `GStreamerCamera` | CSI camera via `nvarguscamerasrc`, `nvvidconv`, `appsink` |
| `UsbCamera` | Webcam USB via `cv2.VideoCapture` |
| `VideoFileCamera` | File video untuk demo/pengujian berulang |
| `open_camera()` | Factory berdasarkan konfigurasi/argumen CLI |
| `_apply_flip()` | Koreksi orientasi (`horizontal`, `vertical`, `rotate180`) |

Interface kamera: `open()`, `read() -> BGR ndarray | None`, `release()`.

### `signrec/detector.py`

`SignDetector.detect(frame) -> Detection | None`

`Detection` menyimpan:
`label`, `confidence`, `bbox`, `center`, `shape`, `color`, `vertices`,
`circularity`, `solidity`, `area`.

Tahapan:

1. Frame diperkecil ke `process_width` (default 640) dengan rasio aspek.
2. Gaussian blur, konversi HSV.
3. Mask per warna (merah punya dua rentang hue 0-10 dan 170-180).
4. Morfologi open + close 3x3.
5. `findContours` external, urut luas terbesar.
6. Convex hull + `approxPolyDP` (epsilon 3% perimeter hull).
7. Filter geometri per bentuk.
8. Skor bentuk, warna, area; pilih kandidat dengan confidence tertinggi.
9. Bounding box dipetakan kembali ke koordinat frame asli.

### `signrec/decision.py`

`DecisionLogic.update(detection) -> DecisionResult`

`DecisionResult`: `sign`, `confidence`, `safe`, `changed`, `reason`,
`candidate`.

State machine:

```
                 confidence >= threshold
   SAFE  ────────────────────────────────────> STABILIZING
     ^                                           │ 5 frame konsisten
     │                                           v
     │                                      SIGN ACTIVE
     │                                           │
     │        8 frame tanpa sign / low conf       │
     └───────────────────────────────────────────┘
```

- `stable_frames` (default 5): jumlah frame berturut-turut sebelum sign
  dianggap valid.
- `missing_frames` (default 8): toleransi sebelum kembali ke safe state.
- `threshold` (default 0.55): confidence minimum.
- LED hanya diubah ketika `active_sign` berubah, sehingga tidak berkedip
  antar-frame.

### `signrec/gpio_led.py`

`LedController.apply(sign, now) -> dict`

- Mapping sign ke warna dari `detector.classes[*].led`.
- Menyalakan satu LED, mematikan dua lainnya.
- `safe_state = "all_off"` (default) atau `"blink_yellow"`.
- Cache state agar penulisan GPIO hanya terjadi saat berubah.
- `close()` mematikan semua LED lalu `GPIO.cleanup()`.
- `simulate=True` untuk pengembangan tanpa GPIO.

### `main.py`

Loop utama:

1. Baca frame.
2. Deteksi.
3. Update decision logic.
4. Terapkan LED.
5. Render overlay.
6. Simpan snapshot saat state berubah.
7. Tulis CSV.
8. Cetak status periodik.
9. Tampilkan window jika display tersedia.
10. Cleanup saat keluar / `Ctrl+C` / durasi habis.

## 3. Rumus Confidence

```
shape_score  = f(jumlah vertex, circularity, extent)
color_score  = min(1, density_mask / 0.50)
area_score   = min(1, sqrt(area / (0.03 * frame_area)))

confidence   = 0.55 * shape_score
             + 0.30 * color_score
             + 0.15 * area_score
```

Contoh nilai:

| Sign | Shape | Color | Area | Confidence |
|---|---|---|---|---|
| STOP dekat | 0.95 | 1.00 | 1.00 | 0.97 |
| SLOW sedang | 0.94 | 1.00 | 0.80 | 0.94 |
| GO jauh redup | 0.95 | 1.00 | 0.50 | 0.95 |

## 4. Filter Geometri

| Bentuk | Aturan |
|---|---|
| Oktagon (STOP) | aspect 0.65-1.45, extent 0.55-0.96, solidity >= 0.58, vertex 7-9 skor tinggi |
| Segitiga (SLOW) | aspect 0.65-1.45, extent 0.32-0.72, solidity >= 0.60, vertex 3 skor tinggi |
| Lingkaran (GO) | aspect 0.70-1.35, extent 0.55-0.90, circularity >= 0.80, solidity >= 0.70 |

Filter ini menolak objek persegi panjang (mis. jendela/kertas kuning) yang
sebelumnya dapat lolos jika hanya melihat warna.

## 5. Keputusan Desain

| Keputusan | Alasan |
|---|---|
| GStreamer/Argus langsung (PyGObject) | OpenCV 3.2 JetPack tidak punya dukungan GStreamer; cara ini terbukti stabil di Jetson Nano. |
| Color + shape, bukan CNN | Tidak perlu TensorFlow/TensorRT, CPU ringan, mudah dikalibrasi, cocok untuk 3 sign yang bentuknya tegas. |
| Confidence berbobot | Memberi nilai yang bisa ditampilkan dan di-threshold, bukan hanya label biner. |
| Debounce + missing frames | Mengurangi kedip akibat noise dan transisi kamera. |
| Safe state all-off | Paling mudah diverifikasi dan tidak menyesatkan pengguna. |
| Mode simulasi GPIO | Memungkinkan unit test dan demo tanpa hardware. |

## 6. Kinerja Terukur

| Skenario | Hasil |
|---|---|
| Detector (640x360, CPU) | ~35-40 ms/frame |
| Overlay | ~2 ms/frame |
| Pipeline penuh kamera CSI | 17-18 FPS |
| Pipeline penuh video demo | ~20 FPS |
| Synthetic benchmark | 54/54 benar, 0/10 false positive |

Kinerja dapat ditingkatkan dengan menurunkan `max_contours`, memperkecil
`process_width`, atau memproses deteksi setiap 2 frame.

## 7. Konfigurasi

Semua parameter ada di `config/config.json`:

- `camera`: tipe, sensor, resolusi, FPS, `process_width`, `flip`.
- `detector`: threshold, area minimum, kernel, bobot confidence, class.
- `colors`: rentang HSV per warna.
- `decision`: `stable_frames`, `missing_frames`.
- `gpio`: mode, pin, active high, safe state, blink rate.
- `output`: direktori log/snapshot, snapshot on change, status interval.
