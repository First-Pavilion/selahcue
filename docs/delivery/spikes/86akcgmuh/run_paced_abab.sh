#!/bin/zsh
# Interleaved A/B/A/B repeat of the paced run (production 512 vs candidate 576, same config for
# interims and finals), so machine-load swings hit both arms alike. Quiet room = the scenario
# 86akcfp3u's 126 s paced lag measurement used.
set -u
S=${0:A:h}
BIN=$S/harness/target/release/rep-loop-spike
WAVS=$S/audio/sermon_community__samantha__r165.wav,$S/audio/sermon_prayer__fred__r195.wav
export SPIKE_SKIP_VERIFY=1
for i in 1 2 3; do
  for c in prod ctx576; do
    out=$S/results/paced_ab${i}_${c}_n${1:-0}.jsonl
    $BIN paced $WAVS $out $c $c ${1:-0} 2> $out.log
    uptime >> $out.log
  done
done
