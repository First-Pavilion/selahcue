"""C-006 mutation battery for 17tnw2b0nkq's trim. Each mutant: back up the file, apply one textual
replacement (must match exactly once), run the WHOLE default lib suite (siblings included, never
--exact), record which tests failed, restore the file byte-for-byte."""
import os
import shutil
import subprocess
import sys

CRATE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                      "..", "..", "implementation", "desktop", "crates",
                                      "selahcue-stt"))
ENGINE = CRATE + "/src/engine.rs"
REP = CRATE + "/src/repetition.rs"

MUTANTS = [
    ("(i) trim applied to every close (reason ignored)", ENGINE,
     "                    CloseReason::Paused | CloseReason::Flushed => seg.text,",
     "                    CloseReason::Paused | CloseReason::Flushed => trim_trailing_repeat(&seg.text).unwrap_or(seg.text),"),
    ("(ii) trim also applied to interims", ENGINE,
     "        let text = text.trim();\n        if !text.is_empty() {",
     "        let trimmed = trim_trailing_repeat(text.trim());\n        let text = trimmed.as_deref().unwrap_or(text.trim());\n        if !text.is_empty() {"),
    ("(iii) trim removed from force-closed finals", ENGINE,
     "                    CloseReason::ForceClosed => match trim_trailing_repeat(&seg.text) {",
     "                    CloseReason::ForceClosed => match None::<String> {"),
    ("(iv) minimum span lowered to 1", REP,
     "pub const MIN_TRIM_SPAN_WORDS: usize = 3;",
     "pub const MIN_TRIM_SPAN_WORDS: usize = 1;"),
    ("(v) hangover+cap on the same frame treated as force-closed", ENGINE,
     "            self.close_utterance(if capped && !paused {",
     "            self.close_utterance(if capped {"),
]

for name, path, old, new in MUTANTS:
    src = open(path).read()
    assert src.count(old) == 1, f"{name}: pattern matched {src.count(old)} times"
    shutil.copyfile(path, path + ".bak")
    try:
        open(path, "w").write(src.replace(old, new))
        r = subprocess.run(["cargo", "test", "--manifest-path", CRATE + "/Cargo.toml", "--lib"],
                           capture_output=True, text=True)
        out = r.stdout + r.stderr
        failed = [l.split()[1] for l in out.splitlines() if l.startswith("test ") and l.endswith("FAILED")]
        msgs = [l.strip() for l in out.splitlines() if "must " in l and ("trimmed" in l or "trim" in l or "never" in l or "altered" in l)]
        verdict = "RED" if r.returncode != 0 and failed else ("COMPILE-ERROR" if r.returncode else "GREEN (mutant survived)")
        print(f"{name}: {verdict}; failed={failed}")
        for m in msgs[:3]:
            print("    ", m[:160])
    finally:
        shutil.move(path + ".bak", path)
print("restored")
sys.exit(0)
