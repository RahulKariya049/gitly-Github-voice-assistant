# recognizer.py

import vosk
import json
import wave
import os
import re
import noisereduce as nr
import numpy as np
import speech_recognition as sr
from functools import wraps
from helpers.cli_ui import show_info,log_error
from scipy.signal import butter, lfilter

# 🔁 Retry decorator
def retry_on_none(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(1, 3):
            result = func(*args, **kwargs)
            if result:
                return result
            print(f"[Gitly]: Try again to speak... (attempt {attempt})")

        log_error("[Gitly]: Voice input failed repeatedly.")
        return None
    return wrapper


# STT Command Cleaner
def clean_command(command: str) -> str:
    corrections = {
        r"\bget push\b": "push",
        r"\bgit bush\b": "push",
        r"\bcheck out\b": "checkout",
        r"\bstart us\b": "status",
        r"\bget log\b": "git log",
        r"\bcommit\b": "commit",
        r"\bcomment\b": "commit",
        r"\bamit\b": "commit",
        r"\bthe drive\b": "d drive",
        r"\bc thrive\b": "c drive",
    }

    # Lowercase input once
    command = command.lower()

    for wrong_pattern, correction in corrections.items():
        command = re.sub(wrong_pattern, correction, command)

    return command


def record_audio():
    recognizer = sr.Recognizer()
    with sr.Microphone(sample_rate=16000) as source:
        print("🎙️ Speak now...")
        audio = recognizer.listen(source)

    # Convert raw bytes to numpy waveform
    try:
        waveform = np.frombuffer(audio.frame_data, dtype=np.int16)

        # Check for silence or garbage input
        if waveform.size == 0:
            return audio, recognizer, "empty"

        # Check if all values are nearly same (could be silence or static)
        if np.all(waveform == waveform[0]):
            return audio, recognizer, "noise"

        return audio, recognizer, "ok"

    except Exception:
        return audio, recognizer, "corrupt"


def bandpass_filter(data, lowcut=300.0, highcut=3400.0, sample_rate=16000, order=5):
    #  Breakdown:

    # nyq = 0.5 * fs
    # Nyquist Frequency = highest frequency that can be resolved (8000 Hz)

    # low / nyq	Normalized frequency for low-cut (300 Hz) → 300/8000 = 0.0375
    # high / nyq	Normalized high-cut (3400 Hz) → 0.425

    # butter(...)	Returns bandpass filter coefficients b and a (from scipy)
    # lfilter(...)	Applies filter to signal using those coefficients
    """
    Apply a bandpass filter to keep only the human voice frequency range.
    Removes low rumbles and high-pitched noise.
    """
    if data.ndim > 1:
        data = np.mean(data, axis=1)  # Make mono

    nyquist = 0.5 * sample_rate

    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')  # Butterworth bandpass filter
    return lfilter(b, a, data)


def reduce_noise(data, sample_rate):
    """
    Apply simple noise reduction using a noise profile.
    Works well for static background hums or fan noise.
    """
    # First 0.5 sec as noise sample
    noise_clip = data[:int(sample_rate * 0.5)]
    reduced = nr.reduce_noise(y=data, sr=sample_rate, y_noise=noise_clip, prop_decrease=1.0)
    return reduced


def normalize_audio(data):
    """
    Normalize audio amplitude to keep signal within [-1, 1] range.
    Prevents clipping and standardizes volume.
    """
    max_val = np.max(np.abs(data))
    if max_val == 0:
        return data
    return data / max_val


def send_to_google_stt(audio_np, sample_rate=16000):
    audio_bytes = (audio_np * 32767).astype(np.int16).tobytes()

    recognizer = sr.Recognizer()
    audio_data = sr.AudioData(audio_bytes, sample_rate, 2)

    try:
        return recognizer.recognize_google(audio_data)
    
    except sr.UnknownValueError:
        return "[Could not understand audio]"
    except sr.RequestError as e:
        return f"[API Error: {e}]"



def send_to_vosk(audio_np: np.ndarray, sample_rate=16000, model_path="STT engine/vosk-model-small-en-us-0.15"):
    # Save temp WAV file
    tmp_path = "temp_input.wav"
    audio_int16 = (audio_np * 32767).astype(np.int16)
    with wave.open(tmp_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

    # Load model
    if not os.path.exists(model_path):
        return "[Model not found]"
    
    model = vosk.Model(model_path)
    rec = vosk.KaldiRecognizer(model, sample_rate)

    with wave.open(tmp_path, 'rb') as wf:
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            rec.AcceptWaveform(data)

    result = json.loads(rec.Result())
    os.remove(tmp_path)
    return result.get("text", "[No transcription]")


# 🧠 Final recognizer using Google STT with retry architecture
@retry_on_none
def recognize_speech():
    audio, recogniser, status = record_audio()
    waveform = np.frombuffer(audio.frame_data, dtype=np.int16)
    if(status == "ok"):
        filterd = bandpass_filter(waveform)

        denoised = reduce_noise(filterd,16000)
        normalised = normalize_audio(denoised)
        
        text = send_to_google_stt(normalised)
        text = clean_command(text)
        print(f"[USER]: {text}")
        return text
    else:
        log_error("Didn't get that")

# @retry_on_none
# def recognize_speech():
#     cmd = input("[USER]: ")
#     return cmd.lower()