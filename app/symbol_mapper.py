from __future__ import annotations

import re
from typing import Dict, List

from app.models import MappingStatus, SymbolMappingEntry


_SUFFIX_PATTERN = re.compile(r"([._-](pro|ecn|raw|std|real|demo))|(\.r$)|(_m$)|(m$)", re.IGNORECASE)


def normalize_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    cleaned = _SUFFIX_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    return cleaned


def _score_pair(source: str, destination: str) -> Dict[str, float]:
    src_norm = normalize_symbol(source)
    dst_norm = normalize_symbol(destination)

    exact = 1.0 if src_norm == dst_norm else 0.0
    starts = 0.5 if dst_norm.startswith(src_norm[:3]) or src_norm.startswith(dst_norm[:3]) else 0.0
    length = max(0.0, 1.0 - (abs(len(src_norm) - len(dst_norm)) * 0.2))

    total = (exact * 0.7) + (starts * 0.2) + (length * 0.1)
    return {
        "exact": round(exact, 3),
        "prefix": round(starts, 3),
        "length": round(length, 3),
        "total": round(total, 3),
    }


def build_initial_mapping(source_symbols: List[str], destination_symbols: List[str]) -> List[SymbolMappingEntry]:
    entries: List[SymbolMappingEntry] = []

    for src_symbol in source_symbols:
        best_dest = None
        best_score = -1.0
        best_breakdown: Dict[str, float] = {}

        for dst_symbol in destination_symbols:
            breakdown = _score_pair(src_symbol, dst_symbol)
            if breakdown["total"] > best_score:
                best_score = breakdown["total"]
                best_dest = dst_symbol
                best_breakdown = breakdown

        status = MappingStatus.UNMAPPED
        if best_score >= 0.9:
            status = MappingStatus.AUTO_CONFIRMED
        elif best_score >= 0.65:
            status = MappingStatus.NEEDS_REVIEW

        entries.append(
            SymbolMappingEntry(
                source_symbol=src_symbol,
                destination_symbol=best_dest if status != MappingStatus.UNMAPPED else None,
                status=status,
                confidence=best_score if best_score > 0 else 0.0,
                score_breakdown=best_breakdown,
            )
        )

    return entries


def merge_with_user_overrides(
    old_entries: List[SymbolMappingEntry],
    new_entries: List[SymbolMappingEntry],
) -> List[SymbolMappingEntry]:
    old_map = {entry.source_symbol: entry for entry in old_entries}
    merged: List[SymbolMappingEntry] = []

    for entry in new_entries:
        previous = old_map.get(entry.source_symbol)
        if previous and previous.user_locked:
            previous.status = MappingStatus.USER_OVERRIDE
            merged.append(previous)
            continue
        merged.append(entry)

    return merged
