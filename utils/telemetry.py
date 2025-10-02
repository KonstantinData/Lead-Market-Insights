"""Unified telemetry setup that works with or without the full OTEL stack."""

from __future__ import annotations

import logging
import os
import random
import threading
from typing import Dict, Optional
from urllib.parse import urlparse

from opentelemetry import trace

try:  # pragma: no cover - real SDK imports may be unavailable in tests
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider as _SdkTracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.sdk.trace.sampling import (
        Decision as _Decision,
        StaticSampler as _StaticSampler,
        TraceIdRatioBased as _TraceIdRatioBased,
    )

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as _HttpSpanExporter,
        )
    except ImportError:  # pragma: no cover - optional dependency
        _HttpSpanExporter = None  # type: ignore[assignment]

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as _GrpcSpanExporter,
        )
    except ImportError:  # pragma: no cover - optional dependency
        _GrpcSpanExporter = None  # type: ignore[assignment]

    _SDK_AVAILABLE = True
except Exception:  # pragma: no cover - exercised in stubbed test envs
    Resource = None  # type: ignore[assignment]
    _SdkTracerProvider = None  # type: ignore[assignment]
    BatchSpanProcessor = None  # type: ignore[assignment]
    ConsoleSpanExporter = None  # type: ignore[assignment]
    SimpleSpanProcessor = None  # type: ignore[assignment]
    _TraceIdRatioBased = None  # type: ignore[assignment]
    _StaticSampler = None  # type: ignore[assignment]
    _Decision = None  # type: ignore[assignment]
    _HttpSpanExporter = None  # type: ignore[assignment]
    _GrpcSpanExporter = None  # type: ignore[assignment]
    _SDK_AVAILABLE = False


_LOG = logging.getLogger(__name__)


# -- Compat hooks --------------------------------------------------------------
if not hasattr(trace, "get_tracer_provider"):
    _TRACE_PROVIDER_HOOK = {"provider": None}

    def _get_tracer_provider():
        return _TRACE_PROVIDER_HOOK["provider"]

    def _set_tracer_provider(provider):
        _TRACE_PROVIDER_HOOK["provider"] = provider

    if not hasattr(trace, "set_tracer_provider"):
        trace.set_tracer_provider = _set_tracer_provider  # type: ignore[attr-defined]
    trace.get_tracer_provider = _get_tracer_provider  # type: ignore[attr-defined]
else:
    try:  # pragma: no cover - defensive guard for exotic runtimes
        trace.get_tracer_provider()
    except Exception:  # pragma: no cover - fallback for stub packages

        def _safe_get():
            return getattr(trace, "_TRACER_PROVIDER", None)

        trace.get_tracer_provider = _safe_get  # type: ignore[attr-defined]


# -- Compat sampling primitives ------------------------------------------------
class _SamplingResult:
    def __init__(self, sampled: bool) -> None:
        self.sampled = sampled
        self.decision = 1 if sampled else 0


class _SamplerBase:
    def should_sample(self, trace_id_hex: str) -> _SamplingResult:
        return _SamplingResult(True)


class _AlwaysOnSampler(_SamplerBase):
    pass


class _AlwaysOffSampler(_SamplerBase):
    def should_sample(self, trace_id_hex: str) -> _SamplingResult:
        return _SamplingResult(False)


class _RatioSampler(_SamplerBase):
    def __init__(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self._threshold = int(self._ratio * (2**64 - 1))

    def should_sample(self, trace_id_hex: str) -> _SamplingResult:
        try:
            value = int(trace_id_hex[-16:], 16)
        except Exception:
            value = random.getrandbits(64)
        return _SamplingResult(value <= self._threshold)


def _build_stub_sampler(ratio: float) -> _SamplerBase:
    if ratio >= 1.0:
        return _AlwaysOnSampler()
    if ratio <= 0.0:
        return _AlwaysOffSampler()
    return _RatioSampler(ratio)


# -- Compat tracer provider ----------------------------------------------------
class _CompatSpanContext:
    def __init__(self, sampled: bool) -> None:
        self.trace_flags = 0x01 if sampled else 0x00


class _CompatSpan:
    def __init__(self, name: str, sampled: bool, attributes: Optional[Dict[str, object]] = None) -> None:
        self.name = name
        self._ctx = _CompatSpanContext(sampled)
        self.attributes = dict(attributes or {})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get_span_context(self):
        return self._ctx


class _CompatTracer:
    def __init__(self, sampler: _SamplerBase) -> None:
        self._sampler = sampler

    def start_as_current_span(self, name: str, *, attributes: Optional[Dict[str, object]] = None, **_ignored):
        trace_id_hex = f"{random.getrandbits(128):032x}"
        sampled = self._sampler.should_sample(trace_id_hex).sampled
        return _CompatSpan(name, sampled, attributes)


class _CompatProvider:
    def __init__(self, sampler: _SamplerBase, resource: Dict[str, str]):
        self._sampler = sampler
        self._resource = resource

    def get_tracer(self, *_args, **_kwargs):
        return _CompatTracer(self._sampler)

    def resource(self) -> Dict[str, str]:
        return self._resource


# -- Helpers ------------------------------------------------------------------
def _parse_resource_kv(raw: Optional[str]) -> Dict[str, str]:
    if not raw:
        return {}
    result: Dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


def _resolve_ratio(explicit: Optional[float]) -> float:
    if explicit is not None:
        value = explicit
    else:
        raw = os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0")
        try:
            value = float(raw)
        except ValueError:
            value = 1.0
    return max(0.0, min(1.0, value))


def _resolve_endpoint(explicit: Optional[str]) -> Optional[str]:
    endpoint = (
        explicit
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    if not endpoint:
        return None
    endpoint = endpoint.strip()
    return endpoint or None


def _normalise_http_endpoint(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme and not parsed.netloc:
        raise ValueError(
            f"Malformed OTLP HTTP endpoint: '{endpoint}'. "
            "URL has a scheme but no network location (netloc)."
        )
    if not endpoint.endswith("/v1/traces"):
        endpoint = f"{endpoint}/v1/traces"
    return endpoint


def _normalise_grpc_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme:
        if parsed.netloc:
            endpoint = parsed.netloc
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/v1/traces"):
        endpoint = endpoint[: -len("/v1/traces")]
    return endpoint


def _create_http_exporter(endpoint: str):
    if _HttpSpanExporter is None:
        return None
    try:
        return _HttpSpanExporter(endpoint=_normalise_http_endpoint(endpoint))
    except Exception as exc:  # pragma: no cover - defensive guard
        _LOG.warning("Failed to initialise OTLP HTTP exporter: %s", exc)
        return None


def _create_grpc_exporter(endpoint: str):
    if _GrpcSpanExporter is None:
        return None
    insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    try:
        return _GrpcSpanExporter(
            endpoint=_normalise_grpc_endpoint(endpoint),
            insecure=insecure,
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        _LOG.warning("Failed to initialise OTLP gRPC exporter: %s", exc)
        return None


def _build_real_sampler(ratio: float):
    if _TraceIdRatioBased is None:
        return None
    if ratio >= 1.0:
        if _StaticSampler is not None and _Decision is not None:
            return _StaticSampler(_Decision.RECORD_AND_SAMPLE)
        return _TraceIdRatioBased(1.0)
    if ratio <= 0.0:
        if _StaticSampler is not None and _Decision is not None:
            return _StaticSampler(_Decision.DROP)
        return _TraceIdRatioBased(0.0)
    return _TraceIdRatioBased(ratio)


def _setup_real_provider(
    *,
    ratio: float,
    resource_attrs: Dict[str, str],
    endpoint: Optional[str],
    use_console_exporter: bool,
):
    if _SdkTracerProvider is None:
        raise RuntimeError("OpenTelemetry SDK is unavailable")

    sampler = _build_real_sampler(ratio)
    provider_kwargs = {}
    if Resource is not None:
        provider_kwargs["resource"] = Resource.create(resource_attrs)
    if sampler is not None:
        provider_kwargs["sampler"] = sampler

    provider = _SdkTracerProvider(**provider_kwargs)

    exporter = None
    resolved_endpoint = _resolve_endpoint(endpoint)
    protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "").strip().lower()

    if resolved_endpoint:
        prefer_grpc = protocol.startswith("grpc")
        prefer_http = not prefer_grpc

        if prefer_http:
            exporter = _create_http_exporter(resolved_endpoint)
            if exporter is None:
                exporter = _create_grpc_exporter(resolved_endpoint)
        else:
            exporter = _create_grpc_exporter(resolved_endpoint)
            if exporter is None:
                exporter = _create_http_exporter(resolved_endpoint)

    if exporter is not None and BatchSpanProcessor is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))

    if use_console_exporter and ConsoleSpanExporter is not None and SimpleSpanProcessor is not None:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return provider


def _setup_stub_provider(
    *,
    ratio: float,
    resource_attrs: Dict[str, str],
):
    sampler = _build_stub_sampler(ratio)
    resource = dict(resource_attrs)
    provider = _CompatProvider(sampler, resource)

    trace.set_tracer_provider(provider)  # type: ignore[arg-type]
    return provider


# -- Public API ----------------------------------------------------------------
_INIT_LOCK = threading.Lock()
_INITIALIZED = False
_COMPAT_LAST_PROVIDER = None


def setup_telemetry(
    *,
    service_name: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    trace_ratio: Optional[float] = None,
    extra_resource_attributes: Optional[Dict[str, str]] = None,
    use_console_exporter: bool = False,
    force: bool = False,
) -> None:
    """Configure tracing with best effort fallbacks for stub environments."""

    global _INITIALIZED, _COMPAT_LAST_PROVIDER

    with _INIT_LOCK:
        if _INITIALIZED and not force:
            return

        resolved_service = service_name or os.getenv("OTEL_SERVICE_NAME", "app")
        ratio = _resolve_ratio(trace_ratio)

        resource_attrs = {
            "service.name": resolved_service,
            "deployment.environment": os.getenv("DEPLOY_ENV", "local"),
        }
        env_extra = _parse_resource_kv(os.getenv("OTEL_EXTRA_RESOURCE_ATTRS"))
        if env_extra:
            resource_attrs.update(env_extra)
        if extra_resource_attributes:
            resource_attrs.update(extra_resource_attributes)

        provider = None
        if _SDK_AVAILABLE:
            try:
                provider = _setup_real_provider(
                    ratio=ratio,
                    resource_attrs=resource_attrs,
                    endpoint=otlp_endpoint,
                    use_console_exporter=use_console_exporter,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                _LOG.warning(
                    "Falling back to compatibility telemetry due to setup error: %s",
                    exc,
                )
                provider = _setup_stub_provider(
                    ratio=ratio,
                    resource_attrs=resource_attrs,
                )
        else:
            provider = _setup_stub_provider(
                ratio=ratio,
                resource_attrs=resource_attrs,
            )

        _COMPAT_LAST_PROVIDER = provider
        _set_provider_ref(provider)

        original_set = getattr(trace, "set_tracer_provider", None)

        def _compat_get_tp():
            return _COMPAT_LAST_PROVIDER

        def _compat_set_tp(p):
            _set_provider_ref(p)
            if callable(original_set):
                try:
                    original_set(p)  # type: ignore[misc]
                except Exception:  # pragma: no cover - defensive guard
                    pass

        trace.get_tracer_provider = _compat_get_tp  # type: ignore[attr-defined]
        trace.set_tracer_provider = _compat_set_tp  # type: ignore[attr-defined]

        _INITIALIZED = True


def _set_provider_ref(provider) -> None:
    global _COMPAT_LAST_PROVIDER
    _COMPAT_LAST_PROVIDER = provider
    hook = globals().get("_TRACE_PROVIDER_HOOK")
    if isinstance(hook, dict):
        hook["provider"] = provider
    try:  # pragma: no cover - depends on runtime internals
        setattr(trace, "_TRACER_PROVIDER", provider)
    except Exception:
        pass
