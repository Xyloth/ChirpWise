from __future__ import annotations

import sqlite3


NORTHEAST_FAMILIES = {
    "Ducks, Geese, and Swans (Anatidae)",
    "New World Quail (Odontophoridae)",
    "Pheasants, Grouse, and Allies (Phasianidae)",
    "Grebes (Podicipedidae)",
    "Pigeons and Doves (Columbidae)",
    "Cuckoos, Roadrunners, and Anis (Cuculidae)",
    "Nightjars and Allies (Caprimulgidae)",
    "Swifts (Apodidae)",
    "Hummingbirds (Trochilidae)",
    "Rails, Gallinules, and Coots (Rallidae)",
    "Cranes (Gruidae)",
    "Plovers and Lapwings (Charadriidae)",
    "Sandpipers and Allies (Scolopacidae)",
    "Gulls, Terns, and Skimmers (Laridae)",
    "Loons (Gaviidae)",
    "Storks (Ciconiidae)",
    "Frigatebirds (Fregatidae)",
    "Boobies and Gannets (Sulidae)",
    "Cormorants and Shags (Phalacrocoracidae)",
    "Pelicans (Pelecanidae)",
    "Bitterns, Herons, and Allies (Ardeidae)",
    "Ibises and Spoonbills (Threskiornithidae)",
    "New World Vultures (Cathartidae)",
    "Osprey (Pandionidae)",
    "Hawks, Eagles, and Kites (Accipitridae)",
    "Owls (Tytonidae)",
    "Owls (Strigidae)",
    "Kingfishers (Alcedinidae)",
    "Woodpeckers (Picidae)",
    "Caracaras and Falcons (Falconidae)",
    "Tyrant Flycatchers (Tyrannidae)",
    "Vireos, Shrike-Babblers, and Erpornis (Vireonidae)",
    "Shrikes (Laniidae)",
    "Jays, Magpies, Crows, and Ravens (Corvidae)",
    "Larks (Alaudidae)",
    "Swallows (Hirundinidae)",
    "Chickadees and Titmice (Paridae)",
    "Nuthatches (Sittidae)",
    "Treecreepers (Certhiidae)",
    "Wrens (Troglodytidae)",
    "Gnatcatchers (Polioptilidae)",
    "Kinglets (Regulidae)",
    "Old World Flycatchers (Muscicapidae)",
    "Thrushes (Turdidae)",
    "Mockingbirds and Thrashers (Mimidae)",
    "Starlings (Sturnidae)",
    "Waxwings (Bombycillidae)",
    "Old World Sparrows (Passeridae)",
    "Wagtails and Pipits (Motacillidae)",
    "Finches, Euphonias, and Allies (Fringillidae)",
    "Longspurs and Snow Buntings (Calcariidae)",
    "New World Sparrows (Passerellidae)",
    "Yellow-breasted Chat (Icteriidae)",
    "Blackbirds (Icteridae)",
    "New World Warblers (Parulidae)",
    "Cardinals, Piranga Tanagers and Allies (Cardinalidae)",
}


SOUTHERN_NAME_HINTS = (
    "florida",
    "carolina",
    "limpkin",
    "ani",
    "mangrove",
    "chuck-will",
    "swallow-tailed",
    "snail kite",
    "roseate spoonbill",
)

WESTERN_NAME_HINTS = (
    "california",
    "pacific",
    "cassin",
    "gambel",
    "mountain",
    "sage",
    "pinyon",
    "steller",
    "black-throated",
    "white-headed",
    "oak titmouse",
    "bushtit",
    "wrentit",
    "phainopepla",
    "pygmy-owl",
)

RARE_EXCLUDE_HINTS = (
    "albatross",
    "auk",
    "booby",
    "tropicbird",
    "frigatebird",
    "shearwater",
    "storm-petrel",
    "petrel",
    "amazon",
    "parrot",
    "parakeet",
    "hummingbird",
    "trogon",
    "elaenia",
    "becard",
    "tityra",
    "euphonia",
    "grassquit",
    "seedeater",
)


def rebuild_region_memberships(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS species_region_membership (
              species_id INTEGER NOT NULL,
              region_id TEXT NOT NULL,
              reason TEXT,
              PRIMARY KEY(species_id, region_id),
              FOREIGN KEY(species_id) REFERENCES species(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("DELETE FROM species_region_membership")
        for row in conn.execute("SELECT id, common_name, family, difficulty FROM species").fetchall():
            regions = classify_species(row["common_name"], row["family"], row["difficulty"])
            for region_id, reason in regions:
                conn.execute(
                    "INSERT OR REPLACE INTO species_region_membership (species_id, region_id, reason) VALUES (?, ?, ?)",
                    (row["id"], region_id, reason),
                )
        for row in conn.execute(
            """
            SELECT DISTINCT species_id, country, latitude, longitude
            FROM recordings
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """
        ).fetchall():
            for region_id in regions_for_recording(row["country"], row["latitude"], row["longitude"]):
                conn.execute(
                    "INSERT OR REPLACE INTO species_region_membership (species_id, region_id, reason) VALUES (?, ?, ?)",
                    (row["species_id"], region_id, "recording coordinates fall inside region"),
                )


def classify_species(common_name: str, family: str | None, difficulty: int | None) -> list[tuple[str, str]]:
    lower = common_name.lower()
    family = family or ""
    difficulty = difficulty or 3
    regions: list[tuple[str, str]] = []

    if family in NORTHEAST_FAMILIES and difficulty <= 4 and not any(hint in lower for hint in RARE_EXCLUDE_HINTS):
        regions.append(("northeast", "common or plausible ABA species for Northeast / Ohio Valley training"))

    if any(hint in lower for hint in SOUTHERN_NAME_HINTS) or family in {
        "Limpkin (Aramidae)",
        "Anhingas (Anhingidae)",
        "Flamingos (Phoenicopteridae)",
    }:
        regions.append(("southeast", "southern specialty or southeastern family"))

    if family in {
        "New World Sparrows (Passerellidae)",
        "Longspurs and Snow Buntings (Calcariidae)",
        "Blackbirds (Icteridae)",
        "Tyrant Flycatchers (Tyrannidae)",
        "Pheasants, Grouse, and Allies (Phasianidae)",
        "New World Quail (Odontophoridae)",
    } and difficulty <= 4:
        regions.append(("central", "central or plains-relevant family"))

    if any(hint in lower for hint in WESTERN_NAME_HINTS) or difficulty >= 3:
        regions.append(("west", "western, rare, or travel-pack species"))

    if not regions:
        regions.append(("west", "default travel-pack species"))
    return regions


def regions_for_recording(country: str | None, latitude: float | None, longitude: float | None) -> list[str]:
    if country not in {"United States", "Canada"} or latitude is None or longitude is None:
        return []
    matched = []
    boxes = {
        "northeast": ((36.0, -90.0, 48.5, -66.0),),
        "southeast": ((24.0, -94.0, 37.5, -75.0),),
        "central": ((25.0, -107.0, 55.5, -89.0),),
        "west": ((30.0, -125.5, 60.5, -102.0), (51.0, -179.9, 72.0, -129.0), (18.5, -161.0, 23.0, -154.0)),
    }
    for region_id, region_boxes in boxes.items():
        for min_lat, min_lon, max_lat, max_lon in region_boxes:
            if min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon:
                matched.append(region_id)
                break
    return matched
