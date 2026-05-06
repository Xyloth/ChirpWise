from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LicenseDecision:
    allowed: bool
    derivative_allowed: bool
    commercial_allowed: bool
    reason: str


def normalize_license(value: str | None) -> str:
    return (value or "").strip().lower().replace("_", "-")


def evaluate_license(
    license_name: str | None,
    license_url: str | None = None,
    *,
    allow_noncommercial: bool = True,
    allow_no_derivatives: bool = True,
    derivative_required: bool = False,
    commercial_build: bool = False,
) -> LicenseDecision:
    text = f"{normalize_license(license_name)} {normalize_license(license_url)}"
    if not text.strip():
        return LicenseDecision(False, False, False, "missing license")

    is_cc0 = "cc0" in text or "publicdomain" in text or "public-domain" in text
    is_nc = "-nc" in text or "noncommercial" in text or "by-nc" in text
    is_nd = "-nd" in text or "noderivatives" in text or "no-derivatives" in text

    derivative_allowed = not is_nd
    commercial_allowed = not is_nc

    if commercial_build and is_nc:
        return LicenseDecision(False, derivative_allowed, False, "commercial build excludes NC license")
    if derivative_required and is_nd:
        return LicenseDecision(False, False, commercial_allowed, "derivative operation excludes ND license")
    if is_nc and not allow_noncommercial:
        return LicenseDecision(False, derivative_allowed, False, "NC license excluded by policy")
    if is_nd and not allow_no_derivatives:
        return LicenseDecision(False, False, commercial_allowed, "ND license excluded by policy")

    if is_cc0:
        return LicenseDecision(True, True, True, "CC0/public domain compatible")
    return LicenseDecision(True, derivative_allowed, commercial_allowed, "license accepted by policy")


def build_attribution(
    *,
    title: str | None,
    recordist: str | None,
    source: str,
    source_recording_id: str,
    source_url: str | None,
    license_name: str | None,
) -> str:
    parts = []
    if title:
        parts.append(title)
    parts.append(f"{source} {source_recording_id}")
    if recordist:
        parts.append(f"recorded by {recordist}")
    if license_name:
        parts.append(f"licensed {license_name}")
    if source_url:
        parts.append(source_url)
    return "; ".join(parts)

