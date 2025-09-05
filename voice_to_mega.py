import sys, os, json, time, queue, threading
import requests, serial, sounddevice as sd
from vosk import Model, KaldiRecognizer

# === CONFIG ===
MODEL_DIR   = os.path.expanduser("~/vosk_models/vosk-model-small-en-us-0.15")
PLAN_URL    = "http://127.0.0.1:8080/plan"  # your FastAPI /plan
SERIAL_PORT = "/dev/ttyACM0"                # Linux example (Mega)
BAUD        = 115200
SAMPLE_RATE = 16000
CHANNELS    = 1

def open_serial():
    ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
    # Mega resets when serial opens; give it a moment
    time.sleep(2)
    return ser

def record_once():
    if not os.path.isdir(MODEL_DIR):
        print(f"[ERR] Vosk model not found at {MODEL_DIR}")
        sys.exit(1)
    model = Model(MODEL_DIR)
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)

    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print("[AUDIO]", status, file=sys.stderr)
        q.put(bytes(indata))

    print("\n[Mic] Recording… press Enter to stop")
    text = ""
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000,
                           dtype="int16", channels=CHANNELS, callback=callback):
        stop = {"flag": False}
        def stop_on_enter():
            input()
            stop["flag"] = True
        threading.Thread(target=stop_on_enter, daemon=True).start()

        while not stop["flag"]:
            data = q.get()
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                seg = res.get("text", "").strip()
                if seg:
                    text += " " + seg
        # final bits
        res = json.loads(rec.FinalResult())
        seg = res.get("text", "").strip()
        if seg:
            text += " " + seg

    return " ".join(text.split()).strip()

def to_plan(text: str) -> dict:
    # Send the transcription to your /plan server (GPT-OSS)
    r = requests.post(PLAN_URL, json={"text": text}, timeout=30)
    r.raise_for_status()
    return r.json()  # e.g. {"cmd":"WATER_ON","ml":200}

def main():
    print("[INFO] Opening serial:", SERIAL_PORT)
    ser = open_serial()
    print("[OK] Connected to Mega. Press Enter to start talking; Enter again to stop.")
    print("     Say things like: 'give me 200 milliliters of water' or 'dispense three pills'.")

    while True:
        try:
            # Wait for user to start a capture
            input("\nPress Enter to capture voice…")
            transcript = record_once()
            if not transcript:
                print("[WARN] Heard nothing. Try again.")
                continue
            print("[STT] Transcript:", transcript)

            # Ask planner (GPT-OSS) for JSON command
            try:
                cmd = to_plan(transcript)
                print("[PLAN] JSON:", cmd)
            except Exception as e:
                print("[ERR] /plan request failed:", e)
                continue

            # Send a single JSON line to Arduino
            line = json.dumps(cmd) + "\n"
            ser.write(line.encode("utf-8"))
            print("[SERIAL] Sent to Mega:", line.strip())

        except KeyboardInterrupt:
            print("\n[EXIT] Bye!")
            break
        except Exception as e:
            print("[ERR]", e)

if __name__ == "__main__":
    main()
