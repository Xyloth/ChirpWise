from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "app").exists():
            return candidate
    return current


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @classmethod
    def discover(cls, start: Path | None = None) -> "ProjectPaths":
        return cls(find_project_root(start))

    @property
    def db_path(self) -> Path:
        return self.root / "data" / "app" / "birdtrainer.sqlite3"

    @property
    def raw_taxonomy_dir(self) -> Path:
        return self.root / "data" / "raw" / "taxonomy"

    @property
    def xeno_metadata_dir(self) -> Path:
        return self.root / "data" / "raw" / "xeno_metadata"

    @property
    def original_audio_dir(self) -> Path:
        return self.root / "data" / "raw" / "xeno_audio_original"

    @property
    def app_audio_dir(self) -> Path:
        return self.root / "data" / "processed" / "audio_app"

    @property
    def clips_dir(self) -> Path:
        return self.root / "data" / "processed" / "clips"

    @property
    def spectrogram_dir(self) -> Path:
        return self.root / "data" / "processed" / "spectrograms"

    @property
    def waveform_dir(self) -> Path:
        return self.root / "data" / "processed" / "waveforms"

    @property
    def manifests_dir(self) -> Path:
        return self.root / "data" / "manifests"

    def ensure(self) -> None:
        for path in [
            self.raw_taxonomy_dir,
            self.xeno_metadata_dir,
            self.original_audio_dir,
            self.app_audio_dir,
            self.clips_dir,
            self.spectrogram_dir,
            self.waveform_dir,
            self.manifests_dir,
            self.db_path.parent,
        ]:
            path.mkdir(parents=True, exist_ok=True)

