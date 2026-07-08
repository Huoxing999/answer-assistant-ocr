import json
import sys
import traceback

import easyocr
import numpy as np
from PIL import Image, ImageOps


_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
    return _reader


def _recognize_file(path):
    image = Image.open(path).convert("L")
    image = ImageOps.autocontrast(image)
    image = image.convert("RGB")
    result = _get_reader().readtext(
        np.array(image),
        detail=0,
        paragraph=True,
        beamWidth=1,
        workers=0,
        min_size=12,
        text_threshold=0.6,
        low_text=0.3,
    )
    return "\n".join(result).strip()


def main():
    for line in sys.stdin:
        try:
            payload = json.loads(line)
            if payload.get("cmd") == "quit":
                break
            if payload.get("cmd") == "warmup":
                _get_reader()
                print(json.dumps({"ok": True, "text": ""}, ensure_ascii=False), flush=True)
                continue
            text = _recognize_file(payload["image"])
            print(json.dumps({"ok": True, "text": text}, ensure_ascii=False), flush=True)
        except Exception:
            print(
                json.dumps({"ok": False, "error": traceback.format_exc()}, ensure_ascii=False),
                flush=True,
            )


if __name__ == "__main__":
    main()
