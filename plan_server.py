# plan_server.py
from fastapi import FastAPI, HTTPException
import requests, json, logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("plan")

OLLAMA_URL = "http://localhost:11434/api/generate"

SYSTEM = """You output ONE of these JSON objects ONLY:
WATER_ON: {"cmd":"WATER_ON","ml":<int 50..250>}
PILL_DISPENSE: {"cmd":"PILL_DISPENSE","count":<int 1..2>}
STOP: {"cmd":"STOP"}void dispenseWaterML(int ml) {
  if (ml < ML_MIN) ml = ML_MIN;
  if (ml > ML_MAX) ml = ML_MAX;

  unsigned long ms = (unsigned long)((ml / ML_PER_SEC) * 1000.0);
  lcdMsg("Water", String(ml) + " ml");

  isDispensing = true;
  pumpOn();
  delay(ms);
  pumpOff();
  isDispensing = false;

  lcdMsg("Water done");
}
STATUS: {"cmd":"STATUS"}
Single object only. No prose. Clamp to ranges. Defaults: ml=150, count=1.
"""

app = FastAPI()

@app.post("/plan")
def plan(payload: dict):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "missing text")

    body = {
        "model": "gpt-oss-20b",
        "format": "json",
        "options": {"temperature": 0},
        "stream": False,  # IMPORTANT: disable streaming
        "prompt": f"System: {SYSTEM}\nUser: {text}\nAssistant:"
    }

    try:
        r = requests.post(OLLAMA_URL, json=body, timeout=120)
        r.raise_for_status()
        data = r.json()
        raw = data.get("response")
        if not raw:
            log.error(f"Ollama returned no 'response': {data}")
            raise HTTPException(502, "LLM returned empty response")
        try:
            obj = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            log.error(f"Failed to parse LLM JSON: {raw}")
            raise HTTPException(502, f"Bad LLM JSON: {raw}") from e

        # Safety clamps
        cmd = obj.get("cmd")
        if cmd == "WATER_ON":
            obj["ml"] = max(50, min(250, int(obj.get("ml", 150))))
        elif cmd == "PILL_DISPENSE":
            obj["count"] = max(1, min(2, int(obj.get("count", 1))))
        elif cmd in ("STOP", "STATUS"):
            pass
        else:
            raise HTTPException(400, f"unknown cmd: {cmd}")

        return obj

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Unhandled error in /plan")
        raise HTTPException(500, f"server error: {e}")
