import sys, json, queue, threading, requests, sounddevice as sd
from vosk import Model, KaldiRecognizer
import os

# === CHANGE THIS PATH IF NEEDED ===
MODEL_DIR = os.path.expanduser("~/vosk_models/vosk-model-small-en-us-0.15")
PLAN_URL  = "http://127.0.0.1:8080/plan"  # your FastAPI /plan endpoint

SAMPLE_RATE = 16000
CHANNELS = 1

def record_once():
    if not os.path.isdir(MODEL_DIR):
        print(f"Vosk model not found at {MODEL_DIR}")
        sys.exit(1)

    q = queue.Queue()
    rec = KaldiRecognizer(Model(MODEL_DIR), SAMPLE_RATE)
    rec.SetWords(True)

    def callback(indata, frames, time, status):
        if status: print(status, file=sys.stderr)
        q.put(bytes(indata))

    print("Listening... (press Enter to stop)")
    text = ""
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000,
                           dtype='int16', channels=CHANNELS, callback=callback):
        stop = {"flag": False}
        def stop_on_enter():
            input()
            stop["flag"] = True
        threading.Thread(target=stop_on_enter, daemon=True).start()

        while not stop["flag"]:
            data = q.get()
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                text += " " + res.get("text","").strip()
        res = json.loads(rec.FinalResult())
        text += " " + res.get("text","").strip()
    return " ".join(text.split()).strip()

def send_to_plan(text: str):
    r = requests.post(PLAN_URL, json={"text": text}, timeout=30)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    print("Press Enter to start, Enter again to stop. Ctrl+C to exit.")
    while True:
        try:
            input()
            transcript = record_once()
            if not transcript:
                print("Heard nothing. Try again.")
                continue
            print("Transcript:", transcript)
            cmd = send_to_plan(transcript)
            print("JSON:", json.dumps(cmd))
        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            print("Error:", e)
