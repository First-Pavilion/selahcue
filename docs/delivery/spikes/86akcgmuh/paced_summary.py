"""One line per paced run (reads every results/paced_*.jsonl)."""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
for p in sorted(glob.glob(os.path.join(HERE, "results", "paced_*.jsonl"))):
    try:
        s = json.loads(open(p).readline())["summary"]
    except (ValueError, KeyError):
        continue
    print(f"{os.path.basename(p):42s} noise={s['noise_rms']:.3f} int={s['interim_cfg']:7s} "
          f"fin={s['final_cfg']:7s} | interim lag mean {s['interim_lag_mean']:.2f} p95 "
          f"{s['interim_lag_p95']:.2f} max {s['interim_lag_max']:.2f} | final lag mean "
          f"{s['final_lag_mean']:.2f} max {s['final_lag_max']:.2f} | forced {s['forced_finals']} @ "
          f"{s['forced_final_ms_mean']:.0f} ms | dropped {s['dropped_samples']} | peak "
          f"{100 * s['handoff_peak_frac']:.0f}%")
