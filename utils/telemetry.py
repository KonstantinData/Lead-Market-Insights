"""
Simplified hardened telemetry setup (compat-only).
- Unabhängig von echten OTel Klassen (funktioniert mit Stub-Paket)
- Eigener Provider + Tracer + Span mit get_span_context()
- Ratio / AlwaysOn / AlwaysOff Sampler
- Optional: OTLP Endpoint wird ignoriert (kann später wieder aktiviert werden)
"""

from __future__ import annotations

import os
import random
import threading
from typing import Dict, Optional

from opentelemetry import trace  # stub oder echt – egal

# Falls das Stub-Modul kein get_tracer_provider hat, fügen wir es hinzu
if not hasattr(trace, "get_tracer_provider"):
    _TRACE_PROVIDER_HOOK = {"provider": None}

    def _get_tracer_provider():
        return _TRACE_PROVIDER_HOOK["provider"]

    def _set_tracer_provider(p):
        _TRACE_PROVIDER_HOOK["provider"] = p

    # set_tracer_provider evtl. schon vorhanden; sonst anlegen
    if not hasattr(trace, "set_tracer_provider"):
        trace.set_tracer_provider = _set_tracer_provider  # type: ignore
    trace.get_tracer_provider = _get_tracer_provider  # type: ignore
else:
    # Wir kapseln trotzdem, damit wir Provider zurückholen können
    try:
        _ = trace.get_tracer_provider()
    except Exception:

        def _safe_get():
            return getattr(trace, "_TRACER_PROVIDER", None)

        trace.get_tracer_provider = _safe_get  # type: ignore


# ---- Sampler & SamplingResult ------------------------------------------------
class _SamplingResult:
    def __init__(self, sampled: bool):
        self.sampled = sampled
        self.decision = 1 if sampled else 0  # kompatibel zu Decision.RECORD_AND_SAMPLE


class _SamplerBase:
    def should_sample(self, trace_id_hex: str) -> _SamplingResult:
        return _SamplingResult(True)

    def desc(self) -> str:
        return "base"


class _AlwaysOnSampler(_SamplerBase):
    def desc(self):
        return "always_on"


class _AlwaysOffSampler(_SamplerBase):
    def should_sample(self, trace_id_hex: str) -> _SamplingResult:
        return _SamplingResult(False)

    def desc(self):
        return "always_off"


class _RatioSampler(_SamplerBase):
    def __init__(self, ratio: float):
        self._ratio = max(0.0, min(1.0, ratio))
        self._threshold = int(self._ratio * (2**64 - 1))

    def should_sample(self, trace_id_hex: str) -> _SamplingResult:
        try:
            value = int(trace_id_hex[-16:], 16)  # letzte 64 bits
        except Exception:
            value = random.getrandbits(64)
        return _SamplingResult(value <= self._threshold)

    def desc(self):
        return f"ratio({self._ratio})"


def _build_sampler(ratio: float) -> _SamplerBase:
    if ratio >= 1.0:
        return _AlwaysOnSampler()
    if ratio <= 0.0:
        return _AlwaysOffSampler()
    return _RatioSampler(ratio)


# ---- Span / Tracer / Provider (Kompatibilitätsschicht) ----------------------
class _CompatSpanContext:
    def __init__(self, sampled: bool):
        # trace_flags bit 0 = sampled
        self.trace_flags = 0x01 if sampled else 0x00


class _CompatSpan:
    def __init__(self, name: str, sampled: bool):
        self.name = name
        self._ctx = _CompatSpanContext(sampled)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_span_context(self):
        return self._ctx


class _CompatTracer:
    def __init__(self, sampler: _SamplerBase):
        self._sampler = sampler

    def start_as_current_span(self, name: str):
        trace_id_hex = f"{random.getrandbits(128):032x}"
        res = self._sampler.should_sample(trace_id_hex)
        return _CompatSpan(name, res.sampled)


class _CompatProvider:
    def __init__(self, sampler: _SamplerBase, resource: Dict[str, str]):
        self._sampler = sampler
        self._resource = resource

    def get_tracer(self, *_, **__):
        return _CompatTracer(self._sampler)

    def resource(self):
        return self._resource


# ---- Parsing Helfer ---------------------------------------------------------
def _parse_resource_kv(raw: Optional[str]) -> Dict[str, str]:
    if not raw:
        return {}
    out: Dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k:
            out[k] = v
    return out


# ---- Public API --------------------------------------------------------------
_INIT_LOCK = threading.Lock()
_INITIALIZED = False


def setup_telemetry(
    *,
    service_name: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,  # aktuell ignoriert (Stub-Umgebung)
    trace_ratio: Optional[float] = None,
    extra_resource_attributes: Optional[Dict[str, str]] = None,
    use_console_exporter: bool = False,  # ignoriert – kein echter Export
    force: bool = False,
) -> None:
    """
    Minimal robuste Initialisierung für Tests mit Stub-OpenTelemetry.
    """
    global _INITIALIZED
    with _INIT_LOCK:
        if _INITIALIZED and not force:
            return

        resolved_service = service_name or os.getenv("OTEL_SERVICE_NAME", "app")
        if trace_ratio is None:
            raw = os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0")
            try:
                trace_ratio = float(raw)
            except ValueError:
                trace_ratio = 1.0
        trace_ratio = max(0.0, min(1.0, trace_ratio))

        sampler = _build_sampler(trace_ratio)

        resource = {
            "service.name": resolved_service,
            "deployment.environment": os.getenv("DEPLOY_ENV", "local"),
        }
        env_extra = _parse_resource_kv(os.getenv("OTEL_EXTRA_RESOURCE_ATTRS"))
        if env_extra:
            resource.update(env_extra)
        if extra_resource_attributes:
            resource.update(extra_resource_attributes)

        provider = _CompatProvider(sampler, resource)
        # global setzen
        trace.set_tracer_provider(provider)  # type: ignore
        # --- Force stable global access (override any stub behavior) ---
        # We keep a module-level reference so tests can retrieve it.
        global _COMPAT_LAST_PROVIDER
        _COMPAT_LAST_PROVIDER = provider

        def _compat_get_tp():
            return _COMPAT_LAST_PROVIDER

        def _compat_set_tp(p):
            global _COMPAT_LAST_PROVIDER
            _COMPAT_LAST_PROVIDER = p

        # Hard override (idempotent)
        trace.get_tracer_provider = _compat_get_tp  # type: ignore[attr-defined]
        trace.set_tracer_provider = _compat_set_tp  # type: ignore[attr-defined]

        # Ensure stored
        trace.set_tracer_provider(provider)

        _INITIALIZED = True
