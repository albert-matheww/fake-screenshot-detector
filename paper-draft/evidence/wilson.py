"""Wilson score intervals (z = 1.96) for the proportions reported from the leave-files-out experiment."""
import math
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)
for name, k, n in (("genuine screenshots flagged, suspicious tier (final)", 4, 73), ("genuine screenshots flagged, evidence tier (final)", 0, 73),
                   ("genuine screenshots flagged, suspicious tier (intermediate model)", 8, 73), ("layout rule: genuine corpus images flagged (final)", 6, 6656),
                   ("layout rule: genuine corpus images flagged (first version)", 135, 6656)):
    lo, hi = wilson(k, n); print(f"{name}: {k}/{n} = {k/n:.1%}, Wilson 95% interval {lo:.1%} to {hi:.1%}")
