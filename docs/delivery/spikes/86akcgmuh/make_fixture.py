"""Cut an engine-level repro fixture: [300 ms silence][10.000 s force-closed window][2.0 s of the
same speaker continuing][600 ms silence], 16 kHz mono PCM16, canonical 44-byte header only
(no LIST/FLLR chunks, no trailing bytes).

The 10 s window is exactly one the REAL SttEngine force-closed on the source recording
(slices_forced.json), and the leading silence is a whole number of 20 ms VAD frames, so the
engine's first voiced frame - and therefore its force-close sample - lands on exactly the same
audio when the test replays the fixture.

usage: make_fixture.py <slice_id> <out.wav>
"""
import json
import os
import struct
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sid, out = sys.argv[1], sys.argv[2]
s = {x["id"]: x for x in json.load(open(os.path.join(HERE, "slices_forced.json")))}[sid]
with wave.open(s["wav"]) as w:
    assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
    w.setpos(s["start"])
    body = w.readframes(s["len"] + 2 * 16000)
lead = b"\x00\x00" * (15 * 320)
tail = b"\x00\x00" * (30 * 320)
pcm = lead + body + tail
with open(out, "wb") as f:
    f.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE")
    f.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16))
    f.write(b"data" + struct.pack("<I", len(pcm)) + pcm)
print(out, os.path.getsize(out), "bytes,", len(pcm) // 2 / 16000, "s; window starts at sample",
      len(lead) // 2, "and force-closes at", len(lead) // 2 + s["len"])
