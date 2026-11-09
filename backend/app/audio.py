"""ffmpeg helpers (imageio-ffmpeg binary; there is no system ffmpeg or ffprobe).

All temp files live under backend/data/tmp (gitignored), never on C:.
"""
from __future__ import annotations

import io
import re
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from . import config

SR_STT = 16000  # Prisma converts everything to 16 kHz mono anyway
STT_NATIVE_EXTS = {"wav", "mp3", "ogg", "flac", "aac", "m4a"}  # accepted by Prisma REST as-is
OGG_ALIASES = {"opus", "oga", "spx"}  # Ogg container, other extension (WhatsApp shares .opus)
STT_MAX_CHUNK_S = 28.0


class AudioError(Exception):
    pass


class AudioTooLong(Exception):
    """An upload longer than config.stt_max_seconds(). Deliberately NOT an AudioError/ValueError, so route
    handlers that turn those into 400/415 let it through to the app handler in main.py (413)."""

    def __init__(self, duration_s: float, max_s: float):
        super().__init__(f"recording is {duration_s:.0f} s; the limit is {max_s:.0f} s")
        self.duration_s, self.max_s = duration_s, max_s

    def as_dict(self) -> dict:
        return {"error": "audio_too_long", "duration_s": round(self.duration_s, 1), "max_s": self.max_s,
                "message": f"The recording is {self.duration_s:.0f} seconds. Please keep it under "
                           f"{self.max_s:.0f} seconds, or send it in parts."}


_ffmpeg: str | None = None


def ffmpeg_exe() -> str:
    global _ffmpeg
    if _ffmpeg is None:
        import imageio_ffmpeg

        _ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    return _ffmpeg


def _tmpdir() -> tempfile.TemporaryDirectory:
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=str(config.TMP_DIR))


def _norm_ext(ext: str) -> str:
    ext = (ext or "").lower().lstrip(".")
    if "/" in ext:  # a MIME type was passed
        ext = ext.split("/")[-1].split(";")[0]
    return {"mpeg": "mp3", "x-wav": "wav", "wave": "wav", "x-m4a": "m4a", "mp4a-latm": "m4a"}.get(ext, ext) or "bin"


def ext_of(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return _norm_ext(filename.rsplit(".", 1)[-1])


def _run(args: list[str], timeout: float = 120.0) -> subprocess.CompletedProcess:
    cmd = [ffmpeg_exe(), "-nostdin", "-hide_banner", *args]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise AudioError(f"ffmpeg timed out after {timeout}s") from exc


def _convert(data: bytes, in_ext: str, out_ext: str, out_args: list[str], in_args: list[str] | None = None) -> bytes:
    if not data:
        raise AudioError("empty audio")
    with _tmpdir() as d:
        src = Path(d) / f"in.{_norm_ext(in_ext)}"
        dst = Path(d) / f"out.{out_ext}"
        src.write_bytes(data)
        p = _run(["-y", *(in_args or []), "-i", str(src), "-vn", *out_args, str(dst)])
        if p.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
            tail = p.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
            raise AudioError("ffmpeg failed: " + " | ".join(tail))
        return dst.read_bytes()


# --------------------------------------------------------------------------- inspection
@dataclass
class Probe:
    container: str | None
    codec: str | None
    sample_rate: int | None
    channels: str | None
    duration_s: float | None
    bitrate_kbps: int | None

    def as_dict(self) -> dict:
        return dict(self.__dict__)


_DUR = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_TIME = re.compile(r"time=\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_INPUT = re.compile(r"Input #0,\s*([^,]+(?:,[^,]+)*?),\s*from")
_STREAM = re.compile(r"Stream #0:\d+.*?Audio:\s*([^,\s]+)[^,]*,\s*(\d+)\s*Hz,\s*([^,]+)")
_BITRATE = re.compile(r"bitrate:\s*(\d+)\s*kb/s")


def _hms(m: re.Match) -> float:
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def probe(data: bytes, ext: str) -> Probe:
    """ffprobe-style inspection by parsing `ffmpeg -i` (no ffprobe in imageio-ffmpeg)."""
    if not data:
        raise AudioError("empty audio")
    with _tmpdir() as d:
        src = Path(d) / f"in.{_norm_ext(ext)}"
        src.write_bytes(data)
        err = _run(["-i", str(src)]).stderr.decode("utf-8", "replace")  # exits 1 (no output): expected
        if "Invalid data found" in err or "Audio:" not in err:
            raise AudioError("not a decodable audio file")
        mi, ms, md, mb = _INPUT.search(err), _STREAM.search(err), _DUR.search(err), _BITRATE.search(err)
        dur = _hms(md) if md else None
        if dur is None:  # e.g. MediaRecorder webm without a duration header: decode to find out
            err2 = _run(["-i", str(src), "-vn", "-f", "null", "-"]).stderr.decode("utf-8", "replace")
            times = _TIME.findall(err2)
            if times:
                h, m_, s = times[-1]
                dur = int(h) * 3600 + int(m_) * 60 + float(s)
        return Probe(
            container=mi.group(1).strip() if mi else None,
            codec=ms.group(1) if ms else None,
            sample_rate=int(ms.group(2)) if ms else None,
            channels=ms.group(3).strip() if ms else None,
            duration_s=round(dur, 3) if dur is not None else None,
            bitrate_kbps=int(mb.group(1)) if mb else None,
        )


def duration_s(data: bytes, ext: str) -> float:
    d = probe(data, ext).duration_s
    if d is None:
        raise AudioError("could not determine duration")
    return d


# --------------------------------------------------------------------------- conversion
def to_ogg_opus(data: bytes, in_ext: str, bitrate: str = "24k", sample_rate: int = 48000) -> bytes:
    """Ogg Opus voice note in WhatsApp's shape: mono, Opus (VoIP mode), ~16-24 kbps, .ogg."""
    if sample_rate not in (8000, 12000, 16000, 24000, 48000):
        raise AudioError("Opus sample rate must be 8/12/16/24/48 kHz")
    return _convert(data, in_ext, "ogg", ["-ac", "1", "-ar", str(sample_rate), "-c:a", "libopus",
                                           "-b:a", bitrate, "-vbr", "on", "-application", "voip",
                                           "-map_metadata", "-1", "-f", "ogg"])


def whatsappify(data: bytes, in_ext: str) -> bytes:
    """Simulate WhatsApp voice-note compression for tests: Opus 16 kbps, mono, 16 kHz, Ogg."""
    return to_ogg_opus(data, in_ext, bitrate="16k", sample_rate=16000)


def to_wav16k(data: bytes, in_ext: str) -> bytes:
    return _convert(data, in_ext, "wav", ["-ac", "1", "-ar", str(SR_STT), "-c:a", "pcm_s16le", "-f", "wav"])


def to_mp3(data: bytes, in_ext: str, bitrate: str = "64k") -> bytes:
    return _convert(data, in_ext, "mp3", ["-ac", "1", "-c:a", "libmp3lame", "-b:a", bitrate, "-f", "mp3"])


def remux_to_ogg(data: bytes, in_ext: str) -> bytes:
    """Lossless container copy, for .opus/.oga files (already Ogg Opus) so Prisma accepts them."""
    return _convert(data, in_ext, "ogg", ["-c:a", "copy", "-f", "ogg"])


def pcm16k(data: bytes, in_ext: str) -> bytes:
    """Decode to raw s16le mono 16 kHz PCM."""
    return _convert(data, in_ext, "raw", ["-ac", "1", "-ar", str(SR_STT), "-f", "s16le", "-c:a", "pcm_s16le"])


def wav_from_pcm(pcm: bytes, sample_rate: int = SR_STT) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def concat_with_gaps(clips: list[tuple[bytes, str]], gap_s: float = 0.8) -> bytes:
    """Join clips into one 16 kHz mono WAV with silence between them (for long-note tests)."""
    gap = b"\x00\x00" * int(SR_STT * gap_s)
    parts = []
    for i, (data, ext) in enumerate(clips):
        if i:
            parts.append(gap)
        parts.append(pcm16k(data, ext))
    return wav_from_pcm(b"".join(parts))


# --------------------------------------------------------------------------- splitting
_SIL_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SIL_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


def detect_silences(data: bytes, ext: str, noise_db: float = -35.0, min_silence_s: float = 0.3) -> list[tuple[float, float]]:
    with _tmpdir() as d:
        src = Path(d) / f"in.{_norm_ext(ext)}"
        src.write_bytes(data)
        err = _run(["-i", str(src), "-vn", "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_s}",
                    "-f", "null", "-"]).stderr.decode("utf-8", "replace")
    starts = [max(0.0, float(x)) for x in _SIL_START.findall(err)]
    ends = [float(x) for x in _SIL_END.findall(err)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None  # trailing silence may have no end line
        out.append((s, e if e is not None else s))
    return out


def plan_cuts(total_s: float, silences: list[tuple[float, float]], max_len_s: float = STT_MAX_CHUNK_S,
              min_len_s: float = 3.0) -> list[tuple[float, float]]:
    """Pure function: chunk [0,total] into pieces <= max_len_s, cutting at silence midpoints
    when one exists in the window, else a hard cut at max_len_s."""
    if total_s <= max_len_s:
        return [(0.0, total_s)]
    mids = sorted((s + e) / 2 for s, e in silences if e >= s)
    chunks, cur = [], 0.0
    while total_s - cur > max_len_s:
        hi = cur + max_len_s
        cands = [m for m in mids if cur + min_len_s <= m <= hi]
        cut = max(cands) if cands else hi
        chunks.append((round(cur, 3), round(cut, 3)))
        cur = cut
    chunks.append((round(cur, 3), round(total_s, 3)))
    return chunks


def split_on_silence(data: bytes, ext: str, max_len_s: float = STT_MAX_CHUNK_S, min_len_s: float = 3.0,
                     noise_db: float = -35.0, min_silence_s: float = 0.3) -> list[dict]:
    """Split audio into <= max_len_s chunks at silences (silencedetect), hard cuts as fallback.

    Returns [{"start_s", "end_s", "audio": wav16k bytes}].
    """
    pcm = pcm16k(data, ext)
    total = len(pcm) / 2 / SR_STT
    sil = detect_silences(data, ext, noise_db, min_silence_s) if total > max_len_s else []
    out = []
    for s, e in plan_cuts(total, sil, max_len_s, min_len_s):
        if e - s < 0.15:
            continue
        a, b = int(s * SR_STT) * 2, int(e * SR_STT) * 2
        out.append({"start_s": s, "end_s": e, "audio": wav_from_pcm(pcm[a:b])})
    return out


def prepare_for_stt(data: bytes, filename: str, max_len_s: float = STT_MAX_CHUNK_S) -> tuple[list[dict], float]:
    """Make any upload acceptable to Prisma REST.

    - native formats (wav/mp3/ogg/flac/aac/m4a) <= max_len_s are sent untouched (no re-encode);
    - .opus/.oga are remuxed to .ogg losslessly;
    - everything else (webm, mp4, 3gp, amr...) or anything longer is decoded to 16 kHz WAV and
      split at silences.
    Returns ([{"filename", "audio", "start_s", "end_s"}], total_duration_s).
    """
    ext = ext_of(filename) or "bin"
    info = probe(data, ext)
    total = info.duration_s
    cap = config.stt_max_seconds()
    if total is not None and total > cap:  # before any split or Gnani call (a 60-min upload = 129 calls)
        raise AudioTooLong(total, cap)
    if ext in OGG_ALIASES:
        data, ext = remux_to_ogg(data, ext), "ogg"
    if ext in STT_NATIVE_EXTS and total is not None and total <= max_len_s:
        return [{"filename": f"clip.{ext}", "audio": data, "start_s": 0.0, "end_s": total}], total
    chunks = split_on_silence(data, ext, max_len_s=max_len_s)
    if total is None:
        total = chunks[-1]["end_s"] if chunks else 0.0
        if total > cap:
            raise AudioTooLong(total, cap)
    return [{"filename": f"chunk{i:02d}.wav", "audio": c["audio"], "start_s": c["start_s"], "end_s": c["end_s"]}
            for i, c in enumerate(chunks)], total


# --------------------------------------------------------------------------- playback / tagging helpers
AUDIO_MIME = {"ogg": "audio/ogg", "opus": "audio/ogg", "oga": "audio/ogg", "webm": "audio/webm", "weba": "audio/webm",
              "mp3": "audio/mpeg", "m4a": "audio/mp4", "mp4": "audio/mp4", "aac": "audio/aac", "wav": "audio/wav",
              "flac": "audio/flac", "3gp": "audio/3gpp", "amr": "audio/amr"}


def playable_copy(data: bytes, ext: str) -> bytes | None:
    """An Ogg copy for <audio> and WhatsApp, or None when the original already plays everywhere.

    webm/weba (Android Chrome MediaRecorder) are remuxed to Ogg without re-encoding (Opus copy);
    if the stream cannot be copied, it is encoded to Ogg Opus. .opus/.oga get a plain .ogg remux.
    """
    ext = _norm_ext(ext)
    if ext in ("webm", "weba"):
        try:
            return _convert(data, ext, "ogg", ["-map", "0:a", "-c:a", "copy", "-f", "ogg"])
        except AudioError:
            return to_ogg_opus(data, ext, bitrate="32k")
    if ext in OGG_ALIASES:
        return remux_to_ogg(data, ext)
    return None


def tag_ogg(data: bytes, tags: dict[str, str]) -> bytes:
    """Write OpusTags (Vorbis comments) without re-encoding: ffmpeg -c copy -metadata k=v."""
    args = ["-map", "0:a", "-c", "copy"]
    for k, v in tags.items():
        args += ["-metadata", f"{k}={v}"]
    return _convert(data, "ogg", "ogg", args + ["-f", "ogg"])


def read_tags(data: bytes, ext: str = "ogg") -> dict[str, str]:
    """Container and stream metadata as printed by `ffmpeg -i` (lower-cased keys)."""
    with _tmpdir() as d:
        src = Path(d) / f"in.{_norm_ext(ext)}"
        src.write_bytes(data)
        err = _run(["-i", str(src)]).stderr.decode("utf-8", "replace")
    out: dict[str, str] = {}
    in_meta = False
    for line in err.splitlines():
        s = line.strip()
        if s.startswith("Metadata:"):
            in_meta = True
            continue
        if in_meta:
            if ":" in s and not s.startswith(("Stream", "Duration", "Input", "At least")):
                k, _, v = s.partition(":")
                out[k.strip().lower()] = v.strip()
            else:
                in_meta = s.startswith("Metadata")
    return out


def placeholder_jpeg(caption: str, color: str = "0xb07850", size: str = "960x720", pattern: str = "plain") -> bytes:
    """Synthetic demo photo: a warm textured surface with a caption bar (never a real photo)."""
    base = f"color=c={color}:s={size}"
    if pattern == "tiles":
        tex = "geq=r='r(X,Y)*(0.82+0.18*gt(mod(X,120),4)*gt(mod(Y,120),4))':g='g(X,Y)*(0.82+0.18*gt(mod(X,120),4)*gt(mod(Y,120),4))':b='b(X,Y)*(0.82+0.18*gt(mod(X,120),4)*gt(mod(Y,120),4))'"
    elif pattern == "wood":
        tex = "geq=r='r(X,Y)*(0.9+0.1*sin(Y/7+sin(X/90)*3))':g='g(X,Y)*(0.9+0.1*sin(Y/7+sin(X/90)*3))':b='b(X,Y)*(0.9+0.1*sin(Y/7+sin(X/90)*3))'"
    else:
        tex = "null"
    safe = re.sub(r"[^A-Za-z0-9 ,.()\-]", "", caption)[:70]
    vf_text = (f"{base},{tex},noise=alls=24:allf=t+u,boxblur=2:1,"
               f"drawbox=x=0:y=ih-84:w=iw:h=84:color=black@0.5:t=fill,"
               f"drawtext=text='{safe}':fontcolor=white:fontsize=30:x=24:y=h-60")
    vf_plain = f"{base},{tex},noise=alls=24:allf=t+u,boxblur=2:1,drawbox=x=0:y=ih-84:w=iw:h=84:color=black@0.5:t=fill"
    with _tmpdir() as d:
        out = Path(d) / "p.jpg"
        for vf in (vf_text, vf_plain):  # drawtext needs a font; fall back to no caption text
            p = _run(["-y", "-f", "lavfi", "-i", vf, "-frames:v", "1", "-update", "1", "-q:v", "4", str(out)])
            if p.returncode == 0 and out.exists() and out.stat().st_size > 0:
                return out.read_bytes()
    raise AudioError("could not generate a placeholder photo")


def mp3_copy(data: bytes, in_ext: str = "ogg", tags: dict[str, str] | None = None, bitrate: str = "64k") -> bytes | None:
    """Local MP3 copy (libmp3lame) for players that cannot play Ogg Opus (older iPhones).

    Returns None when this ffmpeg build has no MP3 encoder: callers then return a null MP3 URL.
    Tags are written as ID3v2.3, so the copy keeps the AI label.
    """
    args = ["-ac", "1", "-c:a", "libmp3lame", "-b:a", bitrate, "-id3v2_version", "3"]
    for k, v in (tags or {}).items():
        args += ["-metadata", f"{k}={v}"]
    try:
        return _convert(data, in_ext, "mp3", args + ["-f", "mp3"])
    except AudioError:
        return None
