"""
Device choice for the small models (classifier, sentence encoders) when the 6 GB laptop GPU
is shared with the Kev judge server (~3.8 GB resident).

  pick_device(min_free_gb)  -> "cuda" if that much GPU memory is free right now, else "cpu"
  LEGALAGENT_DEVICE=cpu|cuda overrides.

Callers also catch torch.OutOfMemoryError at run time and retry on CPU, so a busy GPU makes
a request slower, never failing.
"""
import os


def pick_device(min_free_gb: float = 1.0) -> str:
    forced = os.environ.get("LEGALAGENT_DEVICE")
    if forced in ("cpu", "cuda"):
        return forced
    try:
        import torch
        if not torch.cuda.is_available():
            return "cpu"
        free, _total = torch.cuda.mem_get_info()
        return "cuda" if free / 2**30 >= min_free_gb else "cpu"
    except Exception:
        return "cpu"


def is_oom(exc: BaseException) -> bool:
    return "out of memory" in str(exc).lower() or type(exc).__name__ == "OutOfMemoryError"
