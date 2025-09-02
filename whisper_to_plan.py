# whisper_to_plan.py
import os, time, json, requests, sounddevice as sd, numpy as np
from faster_whisper import WhisperModel

# ---------- CONFIG ----------
PLAN_URL   = "http://127.0.0.1:8080/plan"  # Your FastAPI /plan server
MODEL_SIZE = "small"                       # "tiny", "base", "small" are good on CPU
LANG       = "rw"                          # Kirundi ≈ Kinyarwanda ("rw"); set None to autodetect
REC_SECS   = 4.0                           # seconds to record per sample
SAMPLE_RATE = 16000
# ----------------------------

# Load model (CPU-friendly)
# compute_type="int8" is lean; use "float32" if you want max accuracy (slower)
model = WhisperModel(MODEL_SIZE, compute_type="int8")

def record_clip(seconds=REC_SECS):
    print(f"[Mic] Recording {seconds:.1f}s… speak now")
    audio = sd.rec(int(seconds*SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    return audio.flatten()

def transcribe(audio):
    print("[STT] Transcribing…")
    segments, info = model.transcribe(
        audio, language=LANG, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=300)
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    print(f"[STT] Language: {info.language}  |  Conf: {info.language_probability:.2f}")
    return text

def call_plan(text):
    print(f"[PLAN] → {text!r}")
    r = requests.post(PLAN_URL, json={"text": text}, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    print("Press Enter to capture voice. Ctrl+C to exit.")
    while True:
        try:
            input()
            audio = record_clip()
            text = transcribe(audio)
            if not text:
                print("[STT] (empty) — try again.")
                continue
            cmd = call_plan(text)
            print("[JSON]", json.dumps(cmd))
            # Simulate action:
            if cmd.get("cmd") == "WATER_ON":
                print(f"[SIM] Would dispense {cmd['ml']} ml of water")
            elif cmd.get("cmd") == "PILL_DISPENSE":
                print(f"[SIM] Would dispense {cmd['count']} pill(s)")
            elif cmd.get("cmd") == "STOP":
                print("[SIM] Would stop actuators")
            elif cmd.get("cmd") == "STATUS":
                print("[SIM] Would report status")
        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    main()
