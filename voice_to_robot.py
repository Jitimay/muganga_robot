import os, sys, json, queue, threading, requests, sounddevice as sd
from vosk import Model, KaldiRecognizer

# === CONFIG ===
MODEL_DIR = os.path.expanduser("~/vosk_models/vosk-model-small-en-us-0.15")
PLAN_URL  = "http://127.0.0.1:8080/plan"         # your FastAPI /plan
ESP32_URL = "http://192.168.1.50/cmd"            # your ESP32 /cmd endpoint
SAMPLE_RATE, CHANNELS = 16000, 1

def listen_once():
    if not os.path.isdir(MODEL_DIR):
        print(f"Vosk model not found at {MODEL_DIR}"); sys.exit(1)
    q = queue.Queue()
    rec = KaldiRecognizer(Model(MODEL_DIR), SAMPLE_RATE); rec.SetWords(True)
    def cb(indata, frames, t, status): q.put(bytes(indata))
    print("Listening… (press Enter to stop)")
    text = ""
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000,
                           dtype='int16', channels=CHANNELS, callback=cb):
        stop = {"flag": False}
        def stop_on_enter(): input(); stop["flag"] = True
        threading.Thread(target=stop_on_enter, daemon=True).start()
        while not stop["flag"]:
            data = q.get()
            if rec.AcceptWaveform(data):
                text += " " + json.loads(rec.Result()).get("text","").strip()
        text += " " + json.loads(rec.FinalResult()).get("text","").strip()
    return " ".join(text.split()).strip()

def to_plan(text:str)->dict:
    r = requests.post(PLAN_URL, json={"text": text}, timeout=30)
    r.raise_for_status(); return r.json()

def to_esp32(cmd:dict):
    r = requests.post(ESP32_URL, json=cmd, timeout=10)
    print("ESP32:", r.status_code, r.text)

if __name__ == "__main__":
    print("Press Enter to start talking; Enter again to stop. Ctrl+C to quit.")
    while True:
        try:
            input()
            transcript = listen_once()
            if not transcript:
                print("Heard nothing."); continue
            print("Transcript:", transcript)
            cmd = to_plan(transcript)
            print("JSON:", json.dumps(cmd))
            # Send to robot automatically:
            to_esp32(cmd)
        except KeyboardInterrupt:
            print("\nBye!"); break
        except Exception as e:
            print("Error:", e)
