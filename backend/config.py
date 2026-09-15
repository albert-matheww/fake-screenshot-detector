"""Configuration for the fake-screenshot-detector backend."""
import os


class Config:
    ELA_QUALITY = int(os.environ.get("ELA_QUALITY", 90))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    ANALYSIS_MAX_DIM = int(os.environ.get("ANALYSIS_MAX_DIM", 1600))

    WEIGHTS = {
        "text_score": 0.35,
        "metadata_score": 0.35,
        # arithmetic_score uses the exact same "min(1.0, 0.9 * len(flags))"
        # scoring formula as text_score (see forensic.check_amount_consistency)
        # and the same justification: near-conclusive once it matches
        # something, since it only fires on a mathematical contradiction a
        # real document can't legitimately contain. Weighted the same as
        # text_score for that reason. font_score/edge_score are
        # deliberately NOT here — see their docstrings in forensic.py for
        # why calibration testing didn't support trusting them yet
        # (ghost_score's precedent: computed and shown, excluded from
        # scoring until validated).
        "arithmetic_score": 0.35,
        "clone_score": 0.15,
        "ela_score": 0.08,
        "noise_score": 0.05,
        # chrome_score: real signal (see forensic.check_chrome_consistency)
        # but narrower validation than the cues above and a known,
        # non-trivial false-positive mode on ordinary timestamped content —
        # kept at low weight rather than excluded entirely, similar tier to
        # noise_score.
        "chrome_score": 0.05,
        "quant_score": 0.02,
    }
    FAKE_THRESHOLD = float(os.environ.get("FAKE_THRESHOLD", 0.5))

    # Per-content-type threshold overrides (see forensic.classify_content_type)
    # — looked up by analyze_image_bytes instead of always using
    # FAKE_THRESHOLD. financial_document is raised, not lowered: the
    # README's measured per-source breakdown shows findit2 (receipts) at
    # 28.2% precision / 57.1% recall against the pooled model's one global
    # threshold — i.e. it over-triggers on dense financial/receipt content
    # specifically — so a higher bar for that bucket trades some recall
    # back for precision. photo and social_or_chat are left at the default:
    # casia2 (photo-shaped) already measures well (95.1% F1) at 0.5, and
    # there's no equivalent measured evidence yet for social_or_chat either
    # way. This is a reasoned first pass based on the one breakdown
    # available, not an independently threshold-swept value per bucket —
    # treat 0.55 as a starting point to refine once per-domain validation
    # data (real or synthetic) supports tuning it properly.
    CONTENT_TYPE_THRESHOLDS = {
        "financial_document": 0.55,
    }

    OVERRIDE_CUES = {
        "metadata_score": 0.8,
        "text_score": 0.8,
        # Same override tier as text_score, and for the same reason: a
        # subtotal/total contradiction (see check_amount_consistency) is a
        # document reading, not a pixel-statistics inference, and this
        # project's one prior real false negative (see README's "Known
        # limitations") was specifically a case where pixel cues stayed
        # quiet on a document whose own text gave it away. chrome_score is
        # deliberately NOT an override cue — its score is capped at 0.6 in
        # forensic.check_chrome_consistency precisely so it can never reach
        # this bar, given its acknowledged false-positive risk.
        "arithmetic_score": 0.8,
    }

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
