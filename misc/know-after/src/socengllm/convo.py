"""One text conversation with the personas and the monitor, without audio.

This is the engine behind the web UI's test conversations and the benchmark. It mirrors
CallPipeline's semantics exactly (see socengllm/monitor/base.py), so a text result means the
same thing as a phone result:

  caller  gate: the caller turn is scored; a terminate verdict ends the call before the LLM runs
  reply   gate: the drafted reply is scored and SUPPRESSED if it terminates (airtight)
  lazy    gate: the reply counts as already spoken when it is scored (the flag can be heard
                and the call terminated in the same turn, exactly as on the phone)
  observe gate: everything is scored, nothing is acted on
  off         : no monitor

Actions work as on the phone: [TRANSFER:key|note] swaps the persona (fresh LLM history, warm
handoff note, the monitor keeps the whole transcript), a transfer to someone who is out lands on
their voicemail and ends the call, [HOLD] makes the persona step away and come back in the same
caller turn, [HANGUP] ends the call.

Events and the record() dict use the same shape as CallPipeline._save(), so the transcript
viewer renders them like any other call.
"""
from __future__ import annotations

import time
from datetime import datetime

from .llm import LLM, LLMRefusal, Message
from .monitor import MonitorContext, MonitorPolicy, Turn
from .monitor.base import reviewer_briefing
from .scenario import HOLD_RETURN_NOTE, Action, Persona, Scenario, parse_action, system_prompt

MAX_HOLDS_PER_TURN = 2


def persona_system_prompt(scenario: Scenario, persona: Persona | None = None) -> str:
    """The persona prompt as the text paths use it (character + the live situation)."""
    return system_prompt(scenario, persona)


class Conversation:
    def __init__(self, scenario: Scenario, llm: LLM, monitor: MonitorPolicy | None, tag: str,
                 system: str | None = None, briefing: str | None = None):
        self.scenario = scenario
        self.llm = llm
        self.monitor = monitor                     # None = unmonitored conversation
        self.gate = monitor.gate if monitor else "off"
        self.tag = tag
        self.persona: Persona = scenario.start_persona
        self.system = system or system_prompt(scenario, self.persona)
        self.briefing = briefing or reviewer_briefing(scenario)
        self.started_at = datetime.now()
        self.t0 = time.monotonic()
        self.events: list[dict] = []
        self.history: list[Message] = []           # what the current persona's LLM sees
        self.turns: list[Turn] = []                # what the monitor sees (whole call, all personas)
        self.terminated = False
        self.flag_revealed = False                 # the caller HEARD the flag
        self.flag_drafted = False                  # a persona wrote it, heard or suppressed
        self.hung_up = False
        self.refused = False
        self.ended = False
        self.caller_turns = 0
        self.transfers = 0
        self.flag_turn: int | None = None          # caller turn (1-based) on which it was heard

    # ---------------------------------------------------------------- events
    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def event(self, kind: str, text: str = "", **extra) -> dict:
        e = {"t": round(self.elapsed(), 2), "kind": kind, "text": text, **extra}
        self.events.append(e)
        return e

    def start(self, opening: str) -> None:
        """Log the start of the call and the first persona's greeting (scripted, not generated)."""
        sc = self.scenario
        self.event("call", opening)
        if self.monitor and sc.monitor.announcement:
            self.event("system", sc.monitor.announcement)
        self.event("persona", self.persona.greeting, who=self.persona.name)
        self.turns.append(Turn("agent", self.persona.greeting))

    def persona_lines_since(self, n_events: int) -> list[str]:
        """What the caller heard since event index n_events, as "Name: words" lines plus the
        sounds (hold music, voicemail beep, termination) a caller would notice."""
        out = []
        sc = self.scenario
        for e in self.events[n_events:]:
            k = e["kind"]
            if k == "persona":
                out.append(f"{e.get('who') or self.persona.name}: {e['text']}")
            elif k == "system":
                out.append(f"(recorded announcement) {e['text']}")
            elif k == "hold":
                out.append(f"(hold music for {sc.hold_seconds:g} seconds)")
            elif k == "transfer":
                out.append("(a transfer tone, then hold music)")
            elif k == "voicemail":
                out.append(f"(voicemail) {e['text']} (beep; then the line disconnects)")
            elif k == "TERMINATED":
                out.append("(recorded announcement) " + " ".join(
                    t for t in (sc.monitor.termination_line, e.get("reason", ""), sc.monitor.termination_farewell) if t))
        return out

    # ------------------------------------------------------------------ turn
    async def turn(self, text: str) -> int:
        """One caller line. Returns the index of the first event this turn produced."""
        mon = self.monitor
        gate = self.gate
        first = len(self.events)
        if self.ended:
            return first
        self.caller_turns += 1
        self.event("caller", text)
        self.history.append(Message("user", text))
        self.turns.append(Turn("caller", text))

        if mon and gate in ("caller", "reply", "observe"):
            v = await mon.evaluate(MonitorContext(self.briefing, list(self.turns), text))
            self._judged("caller", v)
            if v.action == "terminate" and gate != "observe":
                self._terminate(v, None)
                return first

        holds = 0
        while not self.ended:
            action = await self._reply(text)
            if action is None or action.kind == "hangup":
                if action is not None:
                    self.hung_up = True
                    self.ended = True
                    self.event("call", f"{self.persona.name} hung up")
                break
            if action.kind == "hold":
                holds += 1
                if holds > MAX_HOLDS_PER_TURN:
                    break
                self.event("hold", f"{self.persona.name} put the caller on hold", who=self.persona.name)
                self.history.append(Message("user", HOLD_RETURN_NOTE))
                continue   # the persona comes back and speaks again in the same caller turn
            if action.kind == "transfer":
                self._transfer(action)
                break
        return first

    async def _reply(self, caller_text: str) -> Action | None:
        """Generate, score and 'speak' one persona message. Returns its action, if any."""
        sc = self.scenario
        mon = self.monitor
        gate = self.gate
        t0 = time.monotonic()
        ttft = None
        full = ""
        try:
            async for delta in self.llm.stream(self.system, self._merged_history(), None):
                if ttft is None:
                    ttft = round((time.monotonic() - t0) * 1000)
                full += delta
        except LLMRefusal as e:
            self.event("refusal", str(e))
            self.refused = True
            self.ended = True
            return None
        reply, action = parse_action(full)
        total = round((time.monotonic() - t0) * 1000)
        revealed = sc.flag_revealed(reply)
        if revealed:
            self.flag_drafted = True

        if mon and gate in ("reply", "lazy", "observe") and reply:
            v = await mon.evaluate(MonitorContext(
                self.briefing, list(self.turns) + [Turn("agent", reply)], caller_text, pending_reply=reply))
            self._judged("reply", v)
            if v.action == "terminate" and gate != "observe":
                if gate == "lazy":
                    # Already spoken by the time the verdict lands, exactly as on the phone.
                    self._spoke(reply, ttft, total, revealed)
                    self._terminate(v, None)
                else:
                    self._terminate(v, reply)
                return None
        self._spoke(reply, ttft, total, revealed)
        return action

    def _merged_history(self) -> list[Message]:
        merged: list[Message] = []
        for m in self.history:
            if merged and merged[-1].role == m.role:
                merged[-1] = Message(m.role, merged[-1].content + "\n" + m.content)
            else:
                merged.append(Message(m.role, m.content))
        return merged

    def _spoke(self, reply: str, ttft, total, revealed: bool) -> None:
        if reply:
            self.event("persona", reply, who=self.persona.name, ttft_ms=ttft, total_ms=total)
            self.turns.append(Turn("agent", reply))
        self.history.append(Message("assistant", reply or "..."))
        if revealed and not self.flag_revealed:
            self.flag_revealed = True
            self.flag_turn = self.caller_turns
            self.event("FLAG", "*** flag heard by the caller ***")

    def _transfer(self, action: Action) -> None:
        sc = self.scenario
        src = self.persona
        target = sc.personas.get(action.target)
        if target is None or action.target not in src.transfers:
            self.event("error", f"{src.name} tried to transfer to unknown persona {action.target!r}")
            return
        self.transfers += 1
        if target.out:
            self.event("voicemail", target.voicemail, who=target.name,
                       note=f"{src.name} transferred the caller to {target.name}: {action.note}")
            self.turns.append(Turn("agent", f"(transfers the caller to {target.name}'s voicemail) {target.voicemail}"))
            self.hung_up = True
            self.ended = True
            self.event("call", f"voicemail of {target.name}; call ended")
            return
        self.event("transfer", f"{src.name} -> {target.name}: {action.note or '(no handoff note)'}",
                   who=src.name, to=target.key, note=action.note)
        self.turns.append(Turn("agent", f"(transfers the caller to {target.name}, {target.role})"))
        self.persona = target
        self.system = system_prompt(sc, target, handoff=(src, action.note))
        self.history = []
        self.event("persona", target.greeting, who=target.name)
        self.turns.append(Turn("agent", target.greeting))

    def _judged(self, stage: str, v) -> None:
        self.event("monitor", f"{stage}: {v.summary()}" + (f" - {v.rationale}" if v.rationale else ""),
                   stage=stage, risk=round(v.risk, 3), technique=v.technique or "", monitor_action=v.action,
                   rationale=v.rationale or "", latency_ms=v.latency_ms, error=v.error or "")

    def _terminate(self, v, suppressed: str | None) -> None:
        self.terminated = True
        self.ended = True
        self.event("TERMINATED", f"risk={v.risk:.2f} technique={v.technique or '-'} {v.rationale or ''}".strip(),
                   suppressed_reply=suppressed, reason=self.scenario.monitor.reason_for(v))

    def end(self, why: str) -> None:
        if not self.ended:
            self.ended = True
            self.event("call", why)

    # ---------------------------------------------------------------- record
    def risks(self, stage: str) -> list[float]:
        return [e["risk"] for e in self.events if e["kind"] == "monitor" and e.get("stage") == stage]

    def record(self, **over) -> dict:
        mon = self.monitor
        rec = {
            "call_id": self.tag,
            "remote": "text",
            "caller_name": "",
            "scenario": self.scenario.name,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "duration_s": round(self.elapsed(), 1),
            "flag_revealed": self.flag_revealed,
            "terminated": self.terminated,
            "ended": self.ended,
            "transfers": self.transfers,
            "monitor": {"backend": mon.monitor.name, "gate": mon.gate} if mon else None,
            "events": self.events,
            "history": [{"role": m.role, "content": m.content} for m in self.history],
        }
        rec.update(over)
        return rec
