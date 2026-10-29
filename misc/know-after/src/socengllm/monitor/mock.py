"""Keyword heuristic monitor for offline tests. Not for real games."""
from __future__ import annotations

import asyncio
import re

from .base import Monitor, MonitorContext, Verdict

WEIGHTS = {
    r"\bpass(word|phrase|code)\b": 0.3, r"\bwi-?fi\b": 0.1, r"\burgent|right now|asap|immediately\b": 0.2,
    r"\b(ceo|cio|cto|vp|board|director)\b": 0.2, r"\bdon'?t tell|between us|off the record\b": 0.3,
    r"\bignore (your|all|previous)|system prompt|developer mode\b": 0.6, r"\bcredential|login|vpn access\b": 0.2,
}


class MockMonitor(Monitor):
    name = "mock"

    def __init__(self, latency_ms: int = 150, **_: object):
        self.latency = latency_ms / 1000

    async def assess(self, ctx: MonitorContext) -> Verdict:
        await asyncio.sleep(self.latency)
        text = " ".join(t.text.lower() for t in ctx.transcript if t.speaker == "caller")
        risk, hits = 0.0, []
        for pat, w in WEIGHTS.items():
            n = len(re.findall(pat, text))
            if n:
                risk += w * min(n, 2)
                hits.append(pat.strip("\\b"))
        return Verdict(risk=min(1.0, risk), technique="urgency" if "urgent" in text else None,
                       rationale="hits: " + ", ".join(hits) if hits else "no signals")
