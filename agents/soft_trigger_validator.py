from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import logging
import math

from utils.text_normalization import normalize_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SoftCandidate:
    soft_trigger: str
    matched_hard_trigger: str
    source_field: str  # "summary" | "description"
    reason: Optional[str] = None


def load_synonym_phrases(path: Path) -> Tuple[str, ...]:
    """Load synonym/paraphrase phrases from a plain text configuration file."""

    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(
            "Synonym trigger configuration file not found at %s. Similarity checks will be disabled.",
            path,
        )
        return ()
    except OSError as exc:  # pragma: no cover - unexpected IO failure
        logger.warning(
            "Failed to read synonym trigger configuration at %s: %s. Similarity checks will be disabled.",
            path,
            exc,
        )
        return ()

    phrases: List[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        phrases.append(line)

    if not phrases:
        logger.warning(
            "Synonym trigger configuration at %s is empty. Similarity checks will rely on evidence only.",
            path,
        )

    return tuple(phrases)


class SoftTriggerValidator:
    """Validate soft trigger candidates returned by the LLM."""

    def __init__(
        self,
        *,
        synonyms: Sequence[str],
        require_evidence_substring: bool = True,
        fuzzy_evidence_threshold: float = 0.88,
        similarity_method: str = "jaccard",
        similarity_threshold: float = 0.60,
    ) -> None:
        self._synonyms_raw: Tuple[str, ...] = tuple(
            s.strip() for s in synonyms if str(s).strip()
        )
        self._synonyms_norm: Tuple[str, ...] = tuple(
            normalize_text(s) for s in self._synonyms_raw
        )
        self.require_evidence_substring = bool(require_evidence_substring)
        self.fuzzy_evidence_threshold = float(fuzzy_evidence_threshold)
        self.similarity_method = str(similarity_method or "jaccard").lower()
        self.similarity_threshold = float(similarity_threshold)

        self._synonym_tokens: Tuple[Tuple[str, ...], ...] = tuple(
            _tokenize(s) for s in self._synonyms_norm
        )
        self._synonym_sets: Tuple[set[str], ...] = tuple(
            set(tokens) for tokens in self._synonym_tokens
        )
        self._synonym_tfidf: Tuple[Dict[str, float], ...]
        self._idf: Dict[str, float]
        self._default_idf: float

        if self._synonym_tokens:
            self._idf = _compute_idf(self._synonym_tokens)
            self._default_idf = math.log((1 + len(self._synonym_tokens)) / 1.0) + 1.0
            self._synonym_tfidf = tuple(
                _tfidf_vector(tokens, self._idf, self._default_idf)
                for tokens in self._synonym_tokens
            )
            self._similarity_disabled = False
        else:
            self._idf = {}
            self._default_idf = 1.0
            self._synonym_tfidf = tuple()
            self._similarity_disabled = True
            logger.warning(
                "SoftTriggerValidator initialised without synonyms; similarity checks will rely on evidence only."
            )

    def validate(
        self,
        *,
        summary: str,
        description: str,
        matches: Sequence[Mapping[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return two lists: (accepted, rejected_with_reasons)."""

        accepted: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for candidate in matches:
            if not isinstance(candidate, Mapping):
                continue

            soft = str(candidate.get("soft_trigger", "")).strip()
            hard = str(candidate.get("matched_hard_trigger", "")).strip()
            source = str(candidate.get("source_field", "")).strip()
            reason_value = candidate.get("reason")
            reason = (
                str(reason_value).strip()
                if reason_value is not None and str(reason_value).strip()
                else None
            )

            if not soft or not hard or source not in {"summary", "description"}:
                rejected.append({**candidate, "reject_reason": "invalid_candidate"})
                continue

            evidence_text = summary if source == "summary" else description or ""
            has_evidence, evidence_kind = self._has_evidence(soft, evidence_text)
            if not has_evidence:
                rejected.append({**candidate, "reject_reason": "no_evidence"})
                continue

            similarity_score = self._max_similarity(soft)
            if (
                not self._similarity_disabled
                and similarity_score < self.similarity_threshold
            ):
                rejected.append(
                    {
                        **candidate,
                        "reject_reason": "low_similarity",
                        "similarity": round(similarity_score, 3),
                    }
                )
                continue

            accepted.append(
                {
                    **candidate,
                    "reason": reason,
                    "validation": {
                        "similarity": round(similarity_score, 3),
                        "method": self.similarity_method,
                        "evidence": evidence_kind,
                    },
                }
            )

        return accepted, rejected

    def _has_evidence(self, phrase: str, text: str) -> Tuple[bool, str]:
        if not self.require_evidence_substring:
            return True, "not_required"
        if not phrase or not text:
            return False, "missing_text"

        normalized_phrase = normalize_text(phrase)
        normalized_text = normalize_text(text)
        if normalized_phrase in normalized_text:
            return True, "substring"

        ratio = self._fuzzy_token_ratio(phrase, text)
        if ratio >= self.fuzzy_evidence_threshold:
            return True, "fuzzy"
        return False, "below_fuzzy_threshold"

    def _max_similarity(self, phrase: str) -> float:
        if self._similarity_disabled:
            return 1.0

        tokens = _tokenize(normalize_text(phrase))
        if not tokens:
            return 0.0

        if self.similarity_method == "jaccard":
            token_set = set(tokens)
            best = 0.0
            for synonym_tokens in self._synonym_sets:
                best = max(best, _jaccard(token_set, synonym_tokens))
            return best

        if self.similarity_method == "tfidf":
            vector = _tfidf_vector(tokens, self._idf, self._default_idf)
            best = 0.0
            for synonym_vector in self._synonym_tfidf:
                best = max(best, _cosine_similarity(vector, synonym_vector))
            return best

        logger.debug(
            "Unknown similarity method '%s'; falling back to Jaccard.",
            self.similarity_method,
        )
        token_set = set(tokens)
        best = 0.0
        for synonym_tokens in self._synonym_sets:
            best = max(best, _jaccard(token_set, synonym_tokens))
        return best

    def _fuzzy_token_ratio(self, phrase: str, text: str) -> float:
        phrase_tokens = set(_tokenize(phrase))
        text_tokens = set(_tokenize(text))
        if not phrase_tokens or not text_tokens:
            return 0.0
        intersection = len(phrase_tokens & text_tokens)
        return intersection / float(len(phrase_tokens))


def _tokenize(text: str) -> Tuple[str, ...]:
    normalised = normalize_text(text)
    normalised = normalised.replace("/", " ").replace("-", " ")
    tokens = tuple(token for token in normalised.split() if token)
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union


def _compute_idf(documents: Sequence[Sequence[str]]) -> Dict[str, float]:
    doc_count = len(documents)
    df: Counter[str] = Counter()
    for doc in documents:
        df.update(set(doc))
    idf: Dict[str, float] = {}
    for token, count in df.items():
        idf[token] = math.log((1 + doc_count) / (1 + count)) + 1.0
    return idf


def _tfidf_vector(
    tokens: Sequence[str], idf: Mapping[str, float], default_idf: float
) -> Dict[str, float]:
    if not tokens:
        return {}
    counts = Counter(tokens)
    length = float(len(tokens))
    vector: Dict[str, float] = {}
    for token, count in counts.items():
        weight = (count / length) * idf.get(token, default_idf)
        vector[token] = weight
    return vector


def _cosine_similarity(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for token, value in a.items():
        dot += value * b.get(token, 0.0)
    if dot == 0.0:
        return 0.0
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


__all__ = [
    "SoftCandidate",
    "SoftTriggerValidator",
    "load_synonym_phrases",
]
