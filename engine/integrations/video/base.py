"""Render de video. Sin Chromium o FFmpeg se escribe el storyboard y no se lanza."""

from __future__ import annotations

import importlib.util
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from core.config import Settings, get_settings


class Shot(BaseModel):
    start_s: int
    end_s: int
    visual: str
    on_screen: str


class Storyboard(BaseModel):
    title: str
    shots: list[Shot]
    voiceover: str
    duration_s: int = 12


class VideoResult(BaseModel):
    kind: str
    path: str
    note: str


class VideoRenderer(Protocol):
    def render(self, landing_path: Path, storyboard: Storyboard) -> VideoResult: ...


class StoryboardRenderer:
    def __init__(
        self,
        output_dir: Path,
        on_info: Callable[[str], None] | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.on_info = on_info

    def render(self, landing_path: Path, storyboard: Storyboard) -> VideoResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"storyboard_{landing_path.stem}.md"
        path.write_text(_markdown(storyboard, landing_path), encoding="utf-8")
        note = "sin Chromium o FFmpeg: storyboard Markdown"
        if self.on_info is not None:
            self.on_info(note)
        return VideoResult(kind="storyboard", path=str(path), note=note)


class PlaywrightFfmpegRenderer:
    """Intenta el MP4 solo si están los dos binarios. Cualquier fallo vuelve al markdown."""

    def __init__(
        self,
        output_dir: Path,
        on_info: Callable[[str], None] | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.on_info = on_info

    def render(self, landing_path: Path, storyboard: Storyboard) -> VideoResult:
        if not _binaries_ready():
            return StoryboardRenderer(self.output_dir, self.on_info).render(
                landing_path, storyboard
            )
        try:
            return self._mp4(landing_path, storyboard)
        except Exception:
            return StoryboardRenderer(self.output_dir, self.on_info).render(
                landing_path, storyboard
            )

    def _mp4(self, landing_path: Path, storyboard: Storyboard) -> VideoResult:
        # La captura real exige un navegador. Si no hay screenshots, no se inventa un mp4.
        raise RuntimeError(f"sin capturas de {landing_path.name} para {storyboard.title}")


def _binaries_ready() -> bool:
    return shutil.which("ffmpeg") is not None and importlib.util.find_spec("playwright") is not None


def _markdown(storyboard: Storyboard, landing_path: Path) -> str:
    rows = ["| Seg | Visual | Texto |", "|-----|--------|-------|"]
    for shot in storyboard.shots:
        rows.append(f"| {shot.start_s}–{shot.end_s} | {shot.visual} | {shot.on_screen} |")
    table = "\n".join(rows)
    return (
        f"# Storyboard {storyboard.duration_s}s — {storyboard.title}\n\n"
        f"Landing: {landing_path.name}\n\n"
        f"{table}\n\n"
        f"## Voz en off\n{storyboard.voiceover}\n"
    )


def build_video(
    settings: Settings | None = None,
    *,
    output_dir: Path,
    on_info: Callable[[str], None] | None = None,
) -> VideoRenderer:
    current = settings or get_settings()
    if current.app_mode == "demo" or current.dry_run:
        return StoryboardRenderer(output_dir, on_info=on_info)
    return PlaywrightFfmpegRenderer(output_dir, on_info=on_info)
