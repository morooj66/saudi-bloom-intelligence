"""Bidirectional-text helpers: wrap Arabic runs in Unicode isolates so mixed Arabic/English/number strings
render in logical order regardless of the surrounding direction."""
import re

FSI, PDI, NBSP = "⁨", "⁩", " "
_AR = "؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿"
_RUN = re.compile(rf"[{_AR}]+(?:[  ]+[{_AR}]+)*")


def isolate(text: str) -> str:
    """Wrap every Arabic run in FSI…PDI. Idempotent. Spaces inside an Arabic phrase become NBSP so the phrase
    cannot wrap across lines (e.g. "محل / ورد" on a narrow screen)."""
    if FSI in text:
        return text
    return _RUN.sub(lambda m: f"{FSI}{re.sub(r'[ ]+', NBSP, m.group(0))}{PDI}", text)


def strip_isolates(text: str) -> str:
    return text.replace(FSI, "").replace(PDI, "")  # NBSP inside Arabic phrases is left as is
