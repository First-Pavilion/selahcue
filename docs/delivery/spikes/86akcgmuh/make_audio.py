"""Render every text with several macOS voices -> 16 kHz mono PCM16 WAV + a manifest.

MEASUREMENT-ONLY audio: `say`-derived, so it is NOT suitable to commit as a fixture
(86akcmmc1 licensing deferral). Each text is rendered by 3 different voices at varied rates
so no single voice/text pairing dominates the slice set.
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
TEXTS = os.path.join(HERE, "texts")
AUDIO = os.path.join(HERE, "audio")
os.makedirs(AUDIO, exist_ok=True)

VOICES = [
    "Samantha", "Daniel", "Karen", "Moira", "Tessa", "Rishi", "Aman", "Tara",
    "Eddy (English (US))", "Flo (English (UK))", "Reed (English (US))", "Sandy (English (UK))",
    "Shelley (English (US))", "Rocko (English (UK))", "Grandpa (English (US))",
    "Grandma (English (UK))", "Albert", "Fred", "Kathy", "Ralph",
]
RATES = [165, 180, 195, 210]
PER_TEXT = 3


def slug(v):
    return re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")


texts = sorted(f[:-4] for f in os.listdir(TEXTS) if f.endswith(".txt"))
manifest = []
k = 0
for ti, name in enumerate(texts):
    ref = open(os.path.join(TEXTS, name + ".txt")).read().strip()
    for j in range(PER_TEXT):
        voice = VOICES[k % len(VOICES)]
        rate = RATES[(k // len(VOICES) + j) % len(RATES)]
        k += 1
        base = f"{name}__{slug(voice)}__r{rate}"
        aiff = os.path.join(AUDIO, base + ".aiff")
        wav = os.path.join(AUDIO, base + ".wav")
        if not os.path.exists(wav):
            subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", aiff, "-f",
                            os.path.join(TEXTS, name + ".txt")], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", aiff, wav],
                           check=True)
            os.remove(aiff)
        manifest.append({"id": base, "wav": wav, "text": name, "voice": voice, "rate": rate,
                         "reference": ref})
        print(base, flush=True)

with open(os.path.join(HERE, "audio_manifest.json"), "w") as f:
    json.dump(manifest, f, indent=1)
print(len(manifest), "recordings")
