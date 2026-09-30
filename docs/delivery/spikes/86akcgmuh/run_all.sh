#!/bin/zsh
# ClickUp 86akcgmuh scoping spike: end-to-end reproduction of every number in the spike's ClickUp
# comment. NOT part of the product and NOT proposed for merge -- it lives on the spike branch so
# the implementer can re-run it. Needs: macOS (`say`, `afconvert`), cmake on PATH, the pinned
# large-v3-turbo model at ~/Library/Caches/selahcue/models, python3. ~2-3 h wall time.
#
# Audio is macOS `say` output (measurement-only; see 86akcmmc1 for why it must not be committed).
# `audio/`, `results/` and `slices_*.json` are generated and deliberately not committed.
#
# Configs (harness `decode` mode) are '+'-joined modifiers on the production params
# (Greedy best_of 1, audio_ctx 512, single_segment true): see harness/src/main.rs's module doc.
set -eu
H=${0:A:h}
cd $H
BIN=$H/harness/target/release/rep-loop-spike
mkdir -p results
python3 make_texts.py
python3 make_audio.py
PATH="/opt/homebrew/bin:$PATH" cargo build --release --manifest-path harness/Cargo.toml
$BIN extract audio_manifest.json results/engine_windows.json
python3 make_slices.py
python3 make_hangover_slices.py
python3 make_latency_slices.py
# The first decode run verifies the model's pinned SHA-256; later runs skip the re-hash.
$BIN decode slices_forced.json results/forced_base.jsonl prod,prod+inst,ss0,unc 2> results/forced_base.log
export SPIKE_SKIP_VERIFY=1
$BIN decode slices_onset10.json results/onset_base.jsonl prod+inst,unc 2> results/onset_base.log
python3 make_subset.py
$BIN decode slices_sweep.json results/sweep1.jsonl prod+inst,cutq1000+inst,cutq500+inst,pad200+inst,beam5+inst,beam3+inst,nots+inst,ngram4,ngram8,ngram12,nofb+inst,best5+inst,ent28+inst 2> results/sweep1.log
$BIN decode slices_sweep.json results/sweep_ctx.jsonl ctx576+inst,ctx640+inst,ctx768+inst,ctx1024+inst,ctx1280+inst 2> results/sweep_ctx.log
$BIN decode slices_hangover.json results/hangover_base.jsonl prod+inst,unc 2> results/hangover_base.log
python3 -c "
import json
on=json.load(open('slices_onset10.json'))
for secs in (8,9):
    json.dump([{**s,'id':s['id'].replace('/10s','/%ds'%secs),'len':secs*16000} for s in on],open('slices_onset%d.json'%secs,'w'))
json.dump(json.load(open('slices_forced.json'))+on, open('slices_all.json','w'))"
$BIN decode slices_onset8.json results/onset8.jsonl prod+inst 2> results/onset8.log
$BIN decode slices_onset9.json results/onset9.jsonl prod+inst 2> results/onset9.log
$BIN decode slices_all.json results/all_levers.jsonl ctx576+inst,ctx640+inst,ctx1024+inst,cutq1000+inst 2> results/all_levers.log
$BIN decode slices_latency.json results/lat_pass1.jsonl prod,ctx576,ctx640,ctx768,ctx1024,unc 2> results/lat_pass1.log
$BIN decode slices_latency.json results/lat_pass2.jsonl ctx1024,ctx576,prod 2> results/lat_pass2.log
zsh run_paced.sh > results/paced_summary.txt
# 17tnw2b0nkq: the SHIPPED code path (production WhisperRecognizer at WHISPER_AUDIO_CTX 576 +
# production trim_trailing_repeat) on every slice, and the ctx change alone; compare/paired pick
# these up automatically. Build the harness against the branch that carries the fix.
$BIN decode slices_all.json results/fix_all.jsonl fix,recog 2> results/fix_all.log
# 17tnw2b0nkq C-009 real-speech validation — ONLY after the user has directly approved the
# download of the six LibriVox MP3s named in real_speech.py into audio_real/:
#   python3 real_speech.py prepare
#   $BIN extract real_manifest.json results/real_engine_windows.json
#   python3 real_speech.py slices
#   $BIN decode slices_real.json results/real.jsonl prod+inst,recog,fix,unc 2> results/real.log
#   python3 real_speech.py report
# Reports:
python3 analyze.py slices_sweep.json audio_manifest.json results/forced_base.jsonl results/onset_base.jsonl results/sweep1.jsonl results/sweep_ctx.jsonl
python3 compare.py
python3 paired.py
python3 latency.py
cat results/paced_summary.txt
