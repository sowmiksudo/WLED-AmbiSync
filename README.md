# 🌈 WLED-AmbiSync: Real-Time Screen & Audio Reactive Backlight

**WLED-AmbiSync** is a high-performance, multi-threaded Python engine that transforms your workstation monitor into a fully immersive, audio-reactive Ambilight display. 

By bypassing cheap factory LED controllers, this script captures screen border pixels at 60 FPS using `mss` and `OpenCV`, analyzes system audio via Windows WASAPI loopback using Fast Fourier Transform (FFT), and streams the synchronized RGB payload to an ESP32 microcontroller running [WLED](https://kno.wled.ge/) over local Wi-Fi.

---

## ✨ Features

* **Zero-Latency Screen Capture:** Uses `mss` and OpenCV's `cv2.resize()` for ultra-fast, matrix-based screen border downscaling.
* **Native Audio Loopback:** Hooks directly into Windows audio using `pyaudiowpatch` (WASAPI), requiring no virtual audio cables or "Stereo Mix."
* **Sub-Bass FFT Analysis:** Processes raw audio buffers to isolate kick drums and sub-bass, dynamically multiplying LED brightness to "punch" to the beat.
* **Multi-Threaded Architecture:** Audio analysis and Screen capture run on independent threads to ensure smooth performance on high-refresh-rate monitors.
* **High-Speed Transport:** Utilizes WLED's Realtime UDP protocol (DRGB/DDP) for near-instantaneous Wi-Fi transmission.

---

## 🛠️ Hardware Requirements

* **Microcontroller:** ESP32 (NodeMCU, Wemos D1 Mini, etc.)
* **LED Strip:** WS2812B Addressable LED Strip (5V)
* **Power Supply:** 5V DC Adapter (e.g., 5V 3A for most monitor setups)
* **Firmware:** [WLED](https://install.wled.me/) installed on the ESP32.

### ⚠️ Wiring (Parallel Power Method)
To protect your ESP32, use a parallel power connection:
1.  **5V Line:** Power Supply (+) ➔ LED Strip 5V **AND** ESP32 `VIN`.
2.  **Ground Line:**