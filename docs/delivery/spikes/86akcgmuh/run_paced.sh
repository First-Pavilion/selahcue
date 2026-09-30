#!/bin/zsh
# Real-time-paced end-to-end runs (see harness `paced` mode). ~130 s of wall time each.
# Stream: two recordings, two voices, not selected for loopiness (first sermon_community voice +
# a sermon_prayer voice). Clean = quiet room (hangover closes most utterances); noisy = 0.012 RMS
# room tone above the EnergyVad floor, so force-close every 10 s is the ONLY close path.
set -u
S=${0:A:h}
BIN=$S/harness/target/release/rep-loop-spike
WAVS=$S/audio/sermon_community__samantha__r165.wav,$S/audio/sermon_prayer__fred__r195.wav
export SPIKE_SKIP_VERIFY=1
for noise in 0.012 0; do
  for pair in "prod prod" "ctx576 ctx576" "prod ctx1024" "prod unc"; do
    set -- ${=pair}
    out=$S/results/paced_${1}_${2}_n${noise}.jsonl
    $BIN paced $WAVS $out $1 $2 $noise 2> $out.log
    grep '^{' $out.log | tail -1
  done
done
