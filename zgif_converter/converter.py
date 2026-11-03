"""FFmpeg decoding and ZGIF packaging; no shell commands are evaluated."""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Callable
import zipfile


class ConversionError(Exception):
    """A conversion failed without publishing a partial output."""


@dataclass(frozen=True)
class Options:
    width: int = 512
    height: int = 512
    fps: int = 15
    quality: int = 3  # FFmpeg JPEG qscale: 2 (best) to 31 (smallest).
    start: float = 0
    duration: float | None = None
    key_color: str = "#00ff00"

    def validate(self) -> None:
        for name, value, low, high in (
            ("幅", self.width, 2, 4096), ("高さ", self.height, 2, 4096),
            ("FPS", self.fps, 1, 120), ("JPEG品質", self.quality, 2, 31),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ConversionError(f"{name}は{low}〜{high}の整数で指定してください。")
        if not math.isfinite(self.start) or self.start < 0:
            raise ConversionError("開始秒は0以上の有限の数で指定してください。")
        if self.duration is not None and (not math.isfinite(self.duration) or self.duration <= 0):
            raise ConversionError("長さは0より大きい有限の秒数で指定してください。")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.key_color):
            raise ConversionError("透過色は #00ff00 のようなRGB値で指定してください。")


def transparency_key(color: str) -> dict:
    """RGB to BT.601 limited-range YCbCr, rounded to 8-bit integers."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return {
        "space": "YCbCr", "matrix": "BT.601", "range": "limited",
        "y": round(16 + (65.481 * r + 128.553 * g + 24.966 * b) / 255),
        "cb": round(128 + (-37.797 * r - 74.203 * g + 112 * b) / 255),
        "cr": round(128 + (112 * r - 93.786 * g - 18.214 * b) / 255),
    }


def find_ffmpeg() -> str:
    override = os.environ.get("ZGIF_FFMPEG")
    if override:
        executable = shutil.which(override)
        if executable:
            return executable
        raise ConversionError("ZGIF_FFMPEGで指定されたFFmpegが見つかりません。")
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise ConversionError(
            "FFmpegが見つかりません。python -m pip install -e . を実行するか、"
            "FFmpegをインストールしてください。"
        ) from exc


def convert(
    source: str | Path, destination: str | Path, options: Options = Options(),
    *, overwrite: bool = False, status: Callable[[str], None] | None = None,
) -> Path:
    options.validate()
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    if not source.is_file():
        raise ConversionError(f"入力ファイルがありません: {source}")
    if destination.suffix.lower() != ".zgif":
        raise ConversionError("出力ファイルの拡張子は .zgif にしてください。")
    if source == destination:
        raise ConversionError("入力と出力には別のファイルを指定してください。")
    if destination.exists() and not overwrite:
        raise ConversionError("出力先が既に存在します。別の名前を指定するか上書きを許可してください。")
    if not destination.parent.is_dir():
        raise ConversionError("出力先のフォルダーがありません。")
    executable = find_ffmpeg()
    report = status or (lambda message: None)
    # A fixed, safe root avoids archive path traversal and encoding differences.
    root = "sticker"
    with tempfile.TemporaryDirectory(prefix="zgif-") as temp:
        frames = Path(temp)
        # Normalize sample aspect ratio before fitting into the target canvas.
        filters = (
            f"fps={options.fps},scale=trunc(iw*sar+0.5):ih,setsar=1,"
            f"scale={options.width}:{options.height}:force_original_aspect_ratio=decrease,"
            f"pad={options.width}:{options.height}:(ow-iw)/2:(oh-ih)/2:"
            f"color=0x{options.key_color[1:]},"
            "scale=in_range=auto:out_range=full:out_color_matrix=bt601,format=yuvj444p"
        )
        command = [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
        if options.start:
            command += ["-ss", str(options.start)]
        command += ["-i", str(source), "-map", "0:v:0", "-an", "-sn", "-dn"]
        if options.duration is not None:
            command += ["-t", str(options.duration)]
        command += ["-vf", filters, "-c:v", "mjpeg", "-q:v", str(options.quality),
                    "-threads", "1", "-start_number", "0", "-f", "image2", str(frames / "%d.jpg")]
        report("動画からフレームを抽出しています…")
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ConversionError(f"FFmpegを起動できません: {exc}") from exc
        if result.returncode:
            raise ConversionError(f"動画の変換に失敗しました。\n{result.stderr[-4000:].strip()}")
        images = sorted(frames.glob("*.jpg"), key=lambda p: int(p.stem))
        if not images:
            raise ConversionError("フレームが生成されませんでした。開始秒・長さ・入力動画を確認してください。")
        metadata = {"version": 1, "width": options.width, "height": options.height,
                    "fps": options.fps, "transparencyKey": transparency_key(options.key_color)}
        report(f"{len(images)}フレームをZGIFにまとめています…")
        # Stage on the destination filesystem; never leave a partial final archive.
        descriptor, staging = tempfile.mkstemp(prefix=".zgif-", suffix=".tmp", dir=destination.parent)
        os.close(descriptor)
        try:
            with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(f"{root}/", b"", compress_type=zipfile.ZIP_STORED)
                for index, image in enumerate(images):
                    archive.write(image, f"{root}/{index}.jpg")
                archive.writestr(f"{root}/gif.json", json.dumps(metadata, indent=2) + "\n")
            if overwrite:
                os.replace(staging, destination)
            else:
                # Exclusive creation also protects a file created during conversion.
                os.link(staging, destination)
        finally:
            Path(staging).unlink(missing_ok=True)
        report(f"完了: {len(images)}フレーム / {destination.stat().st_size:,}バイト")
    return destination
