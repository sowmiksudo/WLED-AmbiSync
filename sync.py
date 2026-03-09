import socket
import threading
import time
import numpy as np
import mss
import cv2
import pyaudiowpatch as pyaudio
import queue
import requests
import json
import os
import collections
from huggingface_hub import hf_hub_download
import onnxruntime as ort
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# --- Global Configuration ---
# Dynamic Configuration overrides
CONFIG = {
    "BASE_BRIGHTNESS": 0.10,
    "BASS_SENSITIVITY": 3.0,
    "FPS_TARGET": 60,
    "WLED_IP": "192.168.1.103",
    "AUDIO_SYNC_ENABLED": True,
    "MANUAL_MOOD": "Smart", # "Smart" or a specific mood like "Mirror", "Nature/Calm", etc.
    "WLED_PORT": 21324,
    "LEDS_LEFT": 40,
    "LEDS_TOP": 70,
    "LEDS_RIGHT": 40,
}

# Calculated from config
DELAY = 1.0 / CONFIG["FPS_TARGET"]
TOTAL_LEDS = CONFIG["LEDS_LEFT"] + CONFIG["LEDS_TOP"] + CONFIG["LEDS_RIGHT"]

# Instead of a global audio_brightness_multiplier, we will track the smoothed pulse explicitly
smoothed_pulse = 0.0

# --- Globals for AI and Cropping ---
frame_queue = queue.Queue(maxsize=2)
current_mood = "Mirror"
crop_bounds = None  # Tracks [rmin, rmax, cmin, cmax] for letterbox cropping

try:
    with open("profiles.json", "r") as f:
        profiles = json.load(f)
except Exception as e:
    print(f"[WARNING] Could not load profiles.json: {e}")
    profiles = { 
        "Static/Text": {"fx": 0, "sx": 128, "ix": 128}
    }

# Load imagenet labels
try:
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("[WARNING] HF_TOKEN environment variable not set. Downloading models might fail if they require authentication.")
    labels_path = hf_hub_download(repo_id="timm/mobilenetv2_100.ra_in1k", filename="config.json", token=hf_token)
    with open(labels_path, "r") as f:
        imagenet_config = json.load(f)
        imagenet_labels = imagenet_config.get("id2label", {})
except Exception as e:
    print(f"[WARNING] Could not load ImageNet labels. AI might output raw class IDs. {e}")
    imagenet_labels = {}

def map_class_to_mood(class_name):
    class_name = class_name.lower()
    if any(k in class_name for k in ['volcano', 'match', 'torch', 'fire', 'lighter', 'projectile', 'racer', 'sports_car', 'military', 'chain_saw', 'weapon', 'tank', 'missile', 'rifle', 'revolver']):
        return "Action/Explosion"
    elif any(k in class_name for k in ['dark', 'night', 'spider', 'web', 'skull', 'bat', 'maze', 'mask', 'cloak', 'coffin', 'guillotine']):
        return "Horror/Dark"
    elif any(k in class_name for k in ['valley', 'alp', 'daisy', 'forest', 'cliff', 'lakeside', 'coral_reef', 'bird', 'dog', 'cat', 'flower', 'ocean', 'lake', 'mountain', 'tree', 'grass']):
        return "Nature/Calm"
    elif any(k in class_name for k in ['monitor', 'screen', 'joystick', 'mouse', 'keyboard', 'computer', 'television', 'gamepad', 'headphone']):
        return "Gaming (Vibrant)"
    elif any(k in class_name for k in ['menu', 'web_site', 'crossword', 'book', 'envelope', 'paper', 'notebook', 'typewriter', 'document']):
        return "Static/Text"
    elif any(k in class_name for k in ['space shuttle', 'planetarium', 'telescope', 'computer', 'modem', 'hard disc', 'radio telescope', 'vacuum', 'robot', 'satellite']):
        return "Sci-Fi / Tech"
    elif any(k in class_name for k in ['football helmet', 'soccer ball', 'tennis racket', 'stadium', 'basketball', 'volleyball', 'running shoe', 'racket', 'dumbbell', 'baseball', 'punching bag']):
        return "Sports / Active"
    elif any(k in class_name for k in ['restaurant', 'suit', 'candle', 'wine glass', 'stage', 'theatre', 'espresso maker', 'gown', 'dining table', 'trench coat', 'sunglasses', 'tie', 'perfume']):
        return "Movie (Drama)"
    else:
        return "Mirror"

def get_mobilenet_onnx():
    print("[AI] Downloading/Verifying MobileNetV2 ONNX model...")
    hf_token = os.environ.get("HF_TOKEN")
    onnx_path = hf_hub_download(repo_id="Kalray/mobilenet-v2", filename="mobilenetv2.onnx", token=hf_token)
    return onnx_path

def preprocess_for_onnx(img):
    # Resize and normalize
    img = cv2.resize(img, (224, 224))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    
    # ImageNet Mean & Std
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img = (img - mean) / std
    
    # HWC to CHW
    img = np.transpose(img, (2, 0, 1))
    
    # Add batch dimension
    img = np.expand_dims(img, axis=0)
    return img

def inference_thread():
    global current_mood
    
    try:
        model_path = get_mobilenet_onnx()
        print("[AI] Loading ONNX model with DirectML/GPU...")
        
        # Try DirectML first, fallback to CPU
        providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
        session = ort.InferenceSession(model_path, providers=providers)
        
        input_name = session.get_inputs()[0].name
        
    except Exception as e:
        print(f"[AI ERROR] Failed to load ONNX model: {e}")
        return
        
    last_mood_change = time.time()
    hysteresis_cooldown = 2.0
    mood_buffer = collections.deque(maxlen=5)
    
    print(f"[AI] Inference Engine ready. Using: {session.get_providers()[0]}")
    while True:
        try:
            frame = frame_queue.get(timeout=1.0)
            
            x = preprocess_for_onnx(frame)
            
            preds = session.run(None, {input_name: x})[0]
            
            # The ONNX mobilenet might output shape [1, 1000]
            top_1_idx = np.argmax(preds[0])
            
            class_name = imagenet_labels.get(str(top_1_idx), str(top_1_idx))
            
            raw_mood = map_class_to_mood(class_name)
            mood_buffer.append(raw_mood)
            
            if CONFIG.get("MANUAL_MOOD", "Smart") == "Smart":
                # Require at least 3 out of 5 frames to agree on the new mood to prevent flickering
                counter = collections.Counter(mood_buffer)
                consensus_mood, count = counter.most_common(1)[0]
                
                if count >= 3 and consensus_mood != current_mood and (time.time() - last_mood_change) > hysteresis_cooldown:
                    print(f"[AI] Scene consensus reached: {class_name} -> Mood: {consensus_mood}")
                    current_mood = consensus_mood
                    last_mood_change = time.time()
                
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[AI ERROR] {e}")
            time.sleep(1)

def audio_listener_thread():
    global smoothed_pulse 
    p = pyaudio.PyAudio()
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        loopback_device = None
        for device in p.get_loopback_device_info_generator():
            if default_speakers["name"] in device["name"]:
                loopback_device = device
                break
        if not loopback_device:
            print("[AUDIO ERROR] Could not find WASAPI loopback device.")
            return
        device_channels = int(loopback_device["maxInputChannels"])
        stream = p.open(format=pyaudio.paFloat32,
                        channels=device_channels,
                        rate=int(loopback_device["defaultSampleRate"]),
                        input=True,
                        frames_per_buffer=1024,
                        input_device_index=loopback_device["index"])
        print(f"[AUDIO] Hooked successfully: Listening to {loopback_device['name']} ({device_channels} channels)")
        while True:
            data = stream.read(1024, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.float32)
            if device_channels > 1:
                audio_data = audio_data[::device_channels]
            
            # Normalize FFT by length to keep bass_amplitude in a generic 0.0 - 0.5 range
            fft_data = np.abs(np.fft.rfft(audio_data)) / len(audio_data)
            bass_amplitude = np.mean(fft_data[1:4])
            
            if CONFIG.get("AUDIO_SYNC_ENABLED", True):
                active_profile = profiles.get(current_mood, profiles.get("Mirror", {}))
                audio_scale = active_profile.get("audio_scale", 1.0)
                
                # The raw amplitude is very small (e.g. 0.001 - 0.005)
                # Scale it up moderately so the UI slider (0-30) is meaningful
                # At slider=10 (default), total multiplier is 1000x
                dynamic_boost = bass_amplitude * CONFIG["BASS_SENSITIVITY"] * 100.0 * audio_scale
            else:
                dynamic_boost = 0.0
            
            target_pulse = min(1.0, dynamic_boost)
            
            # --- 150ms BLUETOOTH DELAY BUFFER ---
            # 1024 frames @ ~48000Hz = ~21.3ms per loop. 150ms / 21.3ms ≈ 7 loops
            if not hasattr(audio_listener_thread, "delay_buffer"):
                audio_listener_thread.delay_buffer = [0.0] * 7
            
            audio_listener_thread.delay_buffer.append(target_pulse)
            delayed_target_pulse = audio_listener_thread.delay_buffer.pop(0)

            # Fast Attack, Faster Release
            if delayed_target_pulse > smoothed_pulse:
                # Attack: Instant response to punchy bass
                alpha = 0.8
            else:
                # Release: Faster fade out so it doesn't linger
                alpha = 0.2
                
            smoothed_pulse = (alpha * delayed_target_pulse) + ((1.0 - alpha) * smoothed_pulse)
    except Exception as e:
        print(f"[AUDIO ERROR] Thread crashed: {e}")
    finally:
        p.terminate()

def remove_black_bars(img_array, threshold=5):
    """
    Intelligently crops black bars (letterboxing/pillarboxing) from the video frame.
    Uses an instant-expand, slow-shrink envelope to prevent jittering during dark scenes.
    """
    global crop_bounds
    h, w = img_array.shape[:2]
    
    if crop_bounds is None:
        crop_bounds = [0, h, 0, w]
        
    gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
    mask = gray > threshold
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    
    if np.any(rows) and np.any(cols):
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]
        
        # Instant Expand (if bright object moves to edge)
        crop_bounds[0] = min(crop_bounds[0], rmin)
        crop_bounds[1] = max(crop_bounds[1], rmax)
        crop_bounds[2] = min(crop_bounds[2], cmin)
        crop_bounds[3] = max(crop_bounds[3], cmax)
        
        # Slow Shrink (1 pixel per frame ≈ 1.5 seconds to adapt at 60fps)
        if crop_bounds[0] < rmin: crop_bounds[0] += 1
        if crop_bounds[1] > rmax: crop_bounds[1] -= 1
        if crop_bounds[2] < cmin: crop_bounds[2] += 1
        if crop_bounds[3] > cmax: crop_bounds[3] -= 1
        
        # Clamp to max 30% crop on each side to prevent collapsing on a tiny object
        crop_bounds[0] = min(crop_bounds[0], int(h * 0.30))
        crop_bounds[1] = max(crop_bounds[1], int(h * 0.70))
        crop_bounds[2] = min(crop_bounds[2], int(w * 0.30))
        crop_bounds[3] = max(crop_bounds[3], int(w * 0.70))
        
    # Apply crop
    r1, r2, c1, c2 = crop_bounds
    return img_array[r1:r2, c1:c2]

def get_border_pixels(img_array):
    h, w, _ = img_array.shape
    
    # 1. Sample deeper into the screen (15%) for richer colors, like premium Ambilight TVs
    depth_x = max(1, int(w * 0.15))
    depth_y = max(1, int(h * 0.15))
    
    # 2. Extract the screen edges
    left_edge = img_array[:, :depth_x, :]
    top_edge = img_array[:depth_y, :, :]
    right_edge = img_array[:, -depth_x:, :]
    
    # 3. Use INTER_AREA to perfectly average all pixels in the zone (prevents flickering)
    # This ensures a small moving white square is averaged smoothly across the nearby LEDs
    left_small = cv2.resize(left_edge, (1, CONFIG["LEDS_LEFT"]), interpolation=cv2.INTER_AREA)
    top_small = cv2.resize(top_edge, (CONFIG["LEDS_TOP"], 1), interpolation=cv2.INTER_AREA)
    right_small = cv2.resize(right_edge, (1, CONFIG["LEDS_RIGHT"]), interpolation=cv2.INTER_AREA)
    
    # 4. Extract into 1D arrays while preserving the strip routing order
    # Left edge: bottom to top
    left_pixels = left_small[::-1, 0, :]
    # Top edge: left to right
    top_pixels = top_small[0, :, :]
    # Right edge: top to bottom
    right_pixels = right_small[:, 0, :]
    
    all_pixels = np.concatenate((left_pixels, top_pixels, right_pixels))
    
    active_profile = profiles.get(current_mood, profiles.get("Mirror", {}))
    bright_scale = active_profile.get("brightness_scale", 1.0)
    
    # Apply brightness scale combined with the pulse
    current_multiplier = min(1.0, (CONFIG["BASE_BRIGHTNESS"] * bright_scale) + smoothed_pulse)
    all_pixels = all_pixels * current_multiplier
    
    # Apply color tint (RGB from config -> BGR logic since cv2 uses BGR)
    tint_rgb = active_profile.get("color_tint", [0, 0, 0])
    if any(c != 0 for c in tint_rgb):
        tint_bgr = np.array([tint_rgb[2], tint_rgb[1], tint_rgb[0]], dtype=float)
        all_pixels = all_pixels + tint_bgr
    
    all_pixels = all_pixels[:, [2, 1, 0]]
    all_pixels = np.clip(all_pixels, 0, 255)
    return all_pixels.flatten().astype(np.uint8)

def stream_av_sync():
    global current_mood
    print(f"[VIDEO] Streaming AV Sync to {CONFIG['WLED_IP']} at {CONFIG['FPS_TARGET']} FPS...")
    print("Press Ctrl+C to stop.")
    UDP_HEADER = bytearray([2, 2])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        try:
            while True:
                sct_img = sct.grab(monitor)
                img_array = np.array(sct_img)[:, :, :3]
                
                # Auto-Crop structural black bars
                img_array = remove_black_bars(img_array)
                
                # Non-blocking put to inference queue
                if not frame_queue.full():
                    try:
                        frame_queue.put_nowait(img_array)
                    except queue.Full:
                        pass
                
                # Stream UDP for all moods, since moods now just tune the pixel data
                pixel_data = get_border_pixels(img_array)
                packet = UDP_HEADER + bytearray(pixel_data)
                sock.sendto(packet, (CONFIG["WLED_IP"], CONFIG["WLED_PORT"]))
                
                time.sleep(DELAY)
        except KeyboardInterrupt:
            print("\nAV Sync Stream stopped.")

def effect_brightness_thread():
    last_sent_bri = -1
    while True:
        # Apply the master brightness across ALL moods scaled by the active profile
        active_profile = profiles.get(current_mood, profiles.get("Mirror", {}))
        bright_scale = active_profile.get("brightness_scale", 1.0)
        target_bri = int(min(1.0, (CONFIG["BASE_BRIGHTNESS"] * bright_scale) + smoothed_pulse) * 255)
        
        if abs(target_bri - last_sent_bri) > 5:
            try:
                # WLED allows master brightness updates while live mode is active
                requests.post(f"http://{CONFIG['WLED_IP']}/json/state", json={"bri": target_bri}, timeout=0.2)
                last_sent_bri = target_bri
            except:
                pass
        time.sleep(0.05)  # Faster updates for smoother audio reactions ~20 FPS

# --- WebUI Backend ---
app = FastAPI()

os.makedirs("web", exist_ok=True)
app.mount("/static", StaticFiles(directory="web"), name="static")

class ConfigUpdate(BaseModel):
    BASE_BRIGHTNESS: float = None
    BASS_SENSITIVITY: float = None
    FPS_TARGET: int = None
    AUDIO_SYNC_ENABLED: bool = None
    MANUAL_MOOD: str = None

@app.get("/api/state")
def get_state():
    return {
        "current_mood": current_mood,
        "config": CONFIG
    }

@app.post("/api/config")
def update_config(update: ConfigUpdate):
    if update.BASE_BRIGHTNESS is not None:
        CONFIG["BASE_BRIGHTNESS"] = update.BASE_BRIGHTNESS
    if update.BASS_SENSITIVITY is not None:
        CONFIG["BASS_SENSITIVITY"] = update.BASS_SENSITIVITY
    if update.FPS_TARGET is not None:
        CONFIG["FPS_TARGET"] = update.FPS_TARGET
        global DELAY
        DELAY = 1.0 / CONFIG["FPS_TARGET"]
    if update.AUDIO_SYNC_ENABLED is not None:
        CONFIG["AUDIO_SYNC_ENABLED"] = update.AUDIO_SYNC_ENABLED
    if update.MANUAL_MOOD is not None:
        CONFIG["MANUAL_MOOD"] = update.MANUAL_MOOD
        if update.MANUAL_MOOD != "Smart":
            global current_mood
            current_mood = update.MANUAL_MOOD
    return {"status": "success", "config": CONFIG}

@app.get("/")
def read_root():
    try:
        with open("web/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard generating...</h1>Refresh in a few seconds.")

def web_server_thread():
    print("[WEB] Starting dashboard at http://127.0.0.1:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="error")

if __name__ == "__main__":
    audio_thread = threading.Thread(target=audio_listener_thread, daemon=True)
    audio_thread.start()
    
    ai_thread = threading.Thread(target=inference_thread, daemon=True)
    ai_thread.start()
    
    bri_thread = threading.Thread(target=effect_brightness_thread, daemon=True)
    bri_thread.start()
    
    web_thread = threading.Thread(target=web_server_thread, daemon=True)
    web_thread.start()
    
    stream_av_sync()