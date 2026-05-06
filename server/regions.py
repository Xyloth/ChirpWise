from __future__ import annotations

from dataclasses import dataclass


BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    countries: tuple[str, ...]
    boxes: tuple[BBox, ...]


REGIONS = [
    Region(
        "northeast",
        "Northeast / Ohio Valley",
        ("United States", "Canada"),
        ((36.0, -90.0, 48.5, -66.0),),
    ),
    Region(
        "southeast",
        "Southeast",
        ("United States",),
        ((24.0, -94.0, 37.5, -75.0),),
    ),
    Region(
        "central",
        "Central / Plains",
        ("United States", "Canada"),
        ((25.0, -107.0, 55.5, -89.0),),
    ),
    Region(
        "west",
        "West / Alaska / Hawaii",
        ("United States", "Canada"),
        (
            (30.0, -125.5, 60.5, -102.0),
            (51.0, -179.9, 72.0, -129.0),
            (18.5, -161.0, 23.0, -154.0),
        ),
    ),
]


def region_options() -> list[dict[str, str]]:
    return [{"id": region.id, "name": region.name} for region in REGIONS]


def get_region(region_id: str | None) -> Region | None:
    if not region_id or region_id == "all":
        return None
    for region in REGIONS:
        if region.id == region_id:
            return region
    return None


def region_recording_condition(region_id: str | None, alias: str = "r") -> tuple[str, list[object]]:
    region = get_region(region_id)
    if not region:
        return "1 = 1", []

    args: list[object] = []
    country_sql = ""
    if region.countries:
        placeholders = ", ".join("?" for _ in region.countries)
        country_sql = f"{alias}.country IN ({placeholders})"
        args.extend(region.countries)

    box_parts = []
    for min_lat, min_lon, max_lat, max_lon in region.boxes:
        box_parts.append(f"({alias}.latitude BETWEEN ? AND ? AND {alias}.longitude BETWEEN ? AND ?)")
        args.extend([min_lat, max_lat, min_lon, max_lon])
    box_sql = "(" + " OR ".join(box_parts) + ")" if box_parts else ""

    if country_sql and box_sql:
        return f"({country_sql} AND {box_sql})", args
    return country_sql or box_sql or "1 = 1", args

