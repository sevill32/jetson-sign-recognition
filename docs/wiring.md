# Dokumentasi Wiring

![Wiring](wiring.png)

Diagram vektor: [`wiring.svg`](wiring.svg).
Generator: `tools/make_diagrams.py`.

## 1. Komponen

| Jumlah | Komponen |
|---|---|
| 1 | NVIDIA Jetson Nano |
| 1 | Kamera CSI IMX219 + kabel ribbon |
| 1 | LED merah |
| 1 | LED kuning |
| 1 | LED hijau |
| 3 | Resistor 1k Ohm |
| 1 | Breadboard |
| 4+ | Kabel jumper female-female |
| 1 | Catu daya 5V 4A (barrel jack) |

## 2. Tabel Koneksi

Menggunakan **BOARD numbering** (nomor pin fisik header 40-pin), sesuai
`"mode": "BOARD"` pada konfigurasi.

| Fungsi | BOARD pin | Nama GPIO | BCM | Komponen |
|---|---|---|---|---|
| STOP / merah | 24 | GPIO18 | 18 | resistor -> anoda LED merah |
| SLOW / kuning | 18 | GPIO12 | 12 | resistor -> anoda LED kuning |
| GO / hijau | 23 | GPIO16 | 16 | resistor -> anoda LED hijau |
| GND | GND | GND | - | katoda semua LED |

Rangkaian per LED:

```
BOARD pin 24/18/23 ── resistor 1k Ohm ── anoda LED ── katoda LED ── GND pin GND
```

## 3. Langkah Wiring

1. **Cabut semua daya** dari Jetson Nano.
2. Pasang kamera CSI pada slot MIPI CSI (kontak kuning menghadap ke arah
   yang benar, kabel jangan dilipat tajam).
3. Pasang tiga LED pada breadboard, catat kaki anoda (kaki panjang) dan
   katoda (kaki pendek / sisi datar).
4. Hubungkan resistor dari pin 24 ke anoda LED merah.
5. Hubungkan resistor dari pin 12 ke anoda LED kuning.
6. Hubungkan resistor dari pin 23 ke anoda LED hijau.
7. Hubungkan semua katoda LED ke rel GND breadboard.
8. Hubungkan rel GND ke **pin GND** Jetson Nano.
9. Periksa kembali dengan multimeter (opsional): tidak ada short antara
   3.3V/5V dan GND.
10. Nyalakan Jetson Nano, lalu uji LED:

```bash
python3 tools/test_leds.py
```

LED akan menyala bergantian: merah -> kuning -> hijau -> semua mati.

Jika LED tidak menyala:

- Periksa polaritas LED.
- Periksa nilai resistor dan koneksi breadboard.
- Pastikan GND bersama terhubung ke pin GND.
- Pastikan pin yang dipakai benar (BOARD vs BCM).
- Coba `python3 tools/test_leds.py --simulate` untuk memastikan software.

## 4. Keamanan

- **Jangan** menghubungkan LED langsung ke pin GPIO tanpa resistor.
- Gunakan resistor 1k Ohm; arus GPIO Jetson Nano terbatas.
- Jangan memberi beban induktif (motor/relay) langsung ke GPIO tanpa
  driver/transistor.
- Cabut daya sebelum mengubah wiring.
- Board uji dapat memunculkan peringatan
  `Carrier board is not from a Jetson Developer Kit`. Verifikasi mapping
  pin header carrier board sebelum menghubungkan LED; jangan mengandalkan
  asumsi pinout dev kit.
- Gunakan catu daya 5V 4A melalui barrel jack untuk menghindari brownout,
  terutama saat kamera dan LED aktif.

## 5. Safe State

Saat tidak ada sign atau confidence di bawah threshold:

- Default: **semua LED OFF**.
- Alternatif: LED kuning berkedip (`"safe_state": "blink_yellow"`).
- Saat program dihentikan (`Ctrl+C`), `main.py` memanggil `LedController.close()`
  yang mematikan semua LED dan membersihkan GPIO.

## 6. Pinout Ringkas Jetson Nano 40-pin (relevan)

| Pin | Fungsi |
|---|---|
| 1 | 3.3V |
| 2 | 5V |
| 6 | GND |
| 7 | GPIO18 (BCM 18) |
| 9 | GND |
| 11 | GPIO12 (BCM 12) |
| 13 | GPIO16 (BCM 16) |
| 14 | GND |
| 20 | GND |
| 25 | GND |
| 30 | GND |
| 34 | GND |
| 39 | GND |

Selalu cocokkan dengan pinout carrier board yang dipakai.
