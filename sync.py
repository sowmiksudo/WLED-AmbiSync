import socket
import threading
import time
import numpy as np
import mss
import cv2
import pyaudiowpatch as pyaudio

WLED_IP = "192.168.1.103"  # REPLACE WITH YOUR ESP32 IP
WLED_PORT = 21324

LEDS_LEFT = 40
LEDS_TOP = 70
LEDS_RIGHT = 40
TOTAL_LEDS = LEDS_LEFT + LEDS_TOP + LEDS_RIGHT

FPS_TARGET = 30
DELAY = 1.0 / FPS_TARGET

BASE_BRIGHTNESS = 0.5
BASS_SENSITIVITY = 10.0

audio_brightness_multiplier = BASE_BRIGHTNESS

def audio_listener_thread():
    global audio_brightness_multiplier 
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
            fft_data = np.abs(np.fft.rfft(audio_data))
            bass_amplitude = np.mean(fft_data[1:4])
            dynamic_boost = bass_amplitude * BASS_SENSITIVITY
            new_multiplier = BASE_BRIGHTNESS + dynamic_boost
            audio_brightness_multiplier = max(BASE_BRIGHTNESS, min(1.0, new_multiplier))
    except Exception as e:
        print(f"[AUDIO ERROR] Thread crashed: {e}")
    finally:
        p.terminate()
def get_border_pixels(sct, monitor):
    sct_img = sct.grab(monitor)
    img_array = np.array(sct_img)[:, :, :3] 
    small_img = cv2.resize(img_array, (LEDS_TOP, LEDS_LEFT))
    left_pixels = small_img[::-1, 0, :]
    top_pixels = small_img[0, :, :]
    right_pixels = small_img[:, -1, :]
    all_pixels = np.concatenate((left_pixels, top_pixels, right_pixels))
    all_pixels = all_pixels * audio_brightness_multiplier
    all_pixels = all_pixels[:, [2, 1, 0]]
    all_pixels = np.clip(all_pixels, 0, 255)
    return all_pixels.flatten().astype(np.uint8)


def stream_av_sync():
    print(f"[VIDEO] Streaming AV Sync to {WLED_IP} at {FPS_TARGET} FPS...")
    print("Press Ctrl+C to stop.")
    UDP_HEADER = bytearray([2, 2])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        try:
            while True:
                pixel_data = get_border_pixels(sct, monitor)
                packet = UDP_HEADER + bytearray(pixel_data)
                sock.sendto(packet, (WLED_IP, WLED_PORT))
                time.sleep(DELAY)
        except KeyboardInterrupt:
            print("\nAV Sync Stream stopped.")


if __name__ == "__main__":
    audio_thread = threading.Thread(target=audio_listener_thread, daemon=True)
    audio_thread.start()
    
    stream_av_sync()