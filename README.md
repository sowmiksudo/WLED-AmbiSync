# 🌈 WLED-AmbiSync: AI-Powered Smart Ambilight

**WLED-AmbiSync** is a high-performance, multi-threaded Python engine that transforms your workstation monitor into a fully immersive, AI-reactive Ambilight display. 

Going beyond standard screen mirroring, this system uses an **AI Scene Classification Engine (MobileNetV2 via ONNX)** to actively analyze what is on your screen in real-time, intelligently adjusting the lighting profile (brightness, color tint, and audio sensitivity) to match the cinematic mood.

All of this is controlled via a beautiful, premium **Glassmorphism Web Dashboard**.

Video Demonstration: [LinkedIn Post](https://www.linkedin.com/posts/sowmiksudo_artificialintelligence-machinelearning-computervision-ugcPost-7436823315102617600-zxQ9)

---

## ✨ Key Features

* **🧠 Smart AI Mood Detection:** Continuously analyzes your screen using Hugging Face's `mobilenet-v2` to detect the scene context (e.g., Action, Horror, Sci-Fi, Sports, Drama, Nature). The AI automatically tunes the WLED output—boosting colors during explosions, dimming the lights for horror movies, or applying a warm cinematic tint for dramas.
* **🎛️ Premium Web Dashboard:** Control the system via a modern, glassmorphism web interface hosted entirely locally (`http://127.0.0.1:5000`). Features a Manual Mood Override dropdown to lock in a specific vibe.
* **⚡ Zero-Latency Screen Capture (Auto-Crop):** Uses `mss` and OpenCV for ultra-fast, matrix-based screen border downscaling. Automatically detects and crops standard movie black bars (letterboxing/pillarboxing) so your LEDs never go dark during ultrawide movies.
* **🎵 Native Audio Loopback:** Hooks directly into Windows audio using `pyaudiowpatch` (WASAPI), requiring no virtual audio cables. Processes raw audio buffers (FFT) to isolate sub-bass, layering a dynamic audio pulse over the visual screen mirror.
* **🚀 Multi-Threaded Architecture:** AI inference, audio analysis, screen capture, and the web server all run on independent threads to ensure ultra-smooth 60+ FPS performance on high-refresh-rate monitors.

---

## 🛠️ Hardware Requirements

* **Microcontroller:** ESP32 (NodeMCU, Wemos D1 Mini, etc.)
* **LED Strip:** WS2812B Addressable LED Strip (5V)
* **Power Supply:** 5V DC Adapter (e.g., 5V 3A for most monitor setups)
* **Firmware:** [WLED](https://install.wled.me/) installed on the ESP32.

---

## 🚀 Installation & Setup

1. **Install Python Dependencies:**
   Ensure you have Python 3.9+ installed on your Windows machine.
   ```bash
   pip install mss opencv-python numpy requests pyaudiowpatch fastapi uvicorn onnxruntime-directml huggingface_hub
   ```

2. **Set Environment Variable (Hugging Face):**
   The AI models are hosted on Hugging Face. You must provide a generic read-access token.
   ```bash
   # Windows PowerShell
   $env:HF_TOKEN="your_hf_access_token"
   ```

3. **Configure Your Application:**
   Open `sync.py` and modify the default global `CONFIG` dictionary at the top to match your setup:
   ```python
   CONFIG = {
       "WLED_IP": "192.168.1.103", # Your ESP32 IP
       "LEDS_LEFT": 40,            # LEDs on your left bezel
       "LEDS_TOP": 70,             # LEDs on your top bezel
       "LEDS_RIGHT": 40,           # LEDs on your right bezel
       # ...
   }
   ```

3. **Start the Engine:**
   Run the python script. It will automatically download the ONNX AI models on first run.
   ```bash
   python sync.py
   ```

4. **Open the Dashboard:**
   Navigate your web browser to `http://127.0.0.1:5000` to access the AmbiSync Control Panel.

---

## 🎬 AI Mood Profiles (`profiles.json`)

The system uses a JSON file to define how different cinematic moods alter the video stream. You can customize these at any time!

* `brightness_scale`: Multiplies the master brightness (e.g., 0.5 for darker horror scenes, 1.5 for bright action scenes).
* `audio_scale`: Multiplies the bass sensitivity (e.g., 1.5 for punchy explosions, 0.3 for quiet dramas).
* `color_tint`: Applies an `[R, G, B]` flat color shift to the LEDs (e.g., adding `[30, 5, -20]` for a warm tungsten movie look).

*Disclaimer: This tool requires a Windows OS environment for native WASAPI audio loopback and DirectML ONNX acceleration.*
