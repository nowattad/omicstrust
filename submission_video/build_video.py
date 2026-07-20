#!/usr/bin/env python3
"""Build the English OmicsTrust Build Week demo video locally."""

from __future__ import annotations

import json
import array
import ctypes
import re
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
import piper
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "submission_video"
ASSET_DIR = VIDEO_DIR / "assets"
SLIDE_DIR = VIDEO_DIR / "slides"
AUDIO_DIR = VIDEO_DIR / "audio"
CLIP_DIR = VIDEO_DIR / "clips"
SEGMENTS_PATH = VIDEO_DIR / "narration_segments.json"
FINAL_VIDEO = VIDEO_DIR / "OmicsTrust_Build_Week_Demo.mp4"

WIDTH = 1920
HEIGHT = 1080
FPS = 30
VOICE = "en-gb-x-rp+m1"
VOICE_RATE = 220

NAVY = "#10233F"
INK = "#17202B"
MUTED = "#5F6B78"
PAPER = "#F7F9FB"
WHITE = "#FFFFFF"
TEAL = "#2F7D73"
TEAL_LIGHT = "#E8F2F0"
AMBER = "#A36B14"
AMBER_LIGHT = "#FAF1DE"
RED = "#A13B3B"
RED_LIGHT = "#F8EAEA"
BLUE = "#2D67A8"
BLUE_LIGHT = "#EAF1F8"
LINE = "#D8E0E8"
SOFT = "#EEF2F6"

FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_MONO = "/System/Library/Fonts/Menlo.ttc"


def font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_MONO if mono else FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(path, size=size)


def text_width(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=face)


def wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or text_width(draw, candidate, face) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    face: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_gap: int = 10,
) -> int:
    x, y = xy
    bbox = face.getbbox("Ag")
    line_height = bbox[3] - bbox[1]
    for line in wrap(draw, text, face, max_width):
        draw.text((x, y), line, font=face, fill=fill)
        y += line_height + line_gap
    return y


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str,
    *,
    outline: str | None = None,
    radius: int = 14,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def base_slide(title: str, caption: str, scene_number: int, *, dark: bool = False) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    bg = NAVY if dark else PAPER
    image = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(image)

    if dark:
        draw.rectangle((0, 0, 16, HEIGHT), fill=TEAL)
        draw.text((90, 54), "OMICS TRUST", font=font(24, bold=True), fill="#BFD8D4")
        draw.text((1510, 54), "OPENAI BUILD WEEK", font=font(22, bold=True), fill="#BFD8D4")
    else:
        draw.rectangle((0, 0, 16, HEIGHT), fill=TEAL)
        draw.text((90, 50), "OMICS TRUST", font=font(24, bold=True), fill=TEAL)
        draw.text((1510, 50), "OPENAI BUILD WEEK", font=font(22, bold=True), fill=MUTED)
        draw.line((90, 92, 1830, 92), fill=LINE, width=2)

    title_fill = WHITE if dark else INK
    caption_fill = "#C7D4E4" if dark else MUTED
    draw.text((90, 128), title, font=font(52, bold=True), fill=title_fill)
    draw.text((92, 198), caption, font=font(27), fill=caption_fill)

    footer_fill = "#0B1A31" if dark else WHITE
    draw.rectangle((0, 948, WIDTH, HEIGHT), fill=footer_fill)
    draw.rectangle((0, 948, 16, HEIGHT), fill=AMBER)
    draw.text((90, 982), f"{scene_number:02d} / 12", font=font(23, bold=True), fill=AMBER if not dark else "#E6B75F")
    draw.text((245, 982), caption, font=font(24), fill=caption_fill)
    draw.text((1657, 982), "RUO ONLY", font=font(23, bold=True), fill=AMBER if not dark else "#E6B75F")
    return image, draw


def fit_image(path: Path, size: tuple[int, int], *, crop: bool = False) -> Image.Image:
    source = Image.open(path).convert("RGB")
    target_w, target_h = size
    if crop:
        source_ratio = source.width / source.height
        target_ratio = target_w / target_h
        if source_ratio > target_ratio:
            new_w = int(source.height * target_ratio)
            left = (source.width - new_w) // 2
            source = source.crop((left, 0, left + new_w, source.height))
        else:
            new_h = int(source.width / target_ratio)
            top = (source.height - new_h) // 2
            source = source.crop((0, top, source.width, top + new_h))
        return source.resize(size, Image.Resampling.LANCZOS)
    source.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, WHITE)
    canvas.paste(source, ((target_w - source.width) // 2, (target_h - source.height) // 2))
    return canvas


def framed_asset(image: Image.Image, draw: ImageDraw.ImageDraw, path: Path, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    draw.rectangle((x1 + 14, y1 + 14, x2 + 14, y2 + 14), fill="#DCE3EA")
    rounded(draw, box, WHITE, outline=LINE, radius=12, width=2)
    content = fit_image(path, (x2 - x1 - 24, y2 - y1 - 24))
    image.paste(content, (x1 + 12, y1 + 12))


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str, color: str) -> int:
    x, y = xy
    face = font(23, bold=True)
    width = int(text_width(draw, text, face)) + 42
    rounded(draw, (x, y, x + width, y + 48), fill, radius=24)
    draw.text((x + 21, y + 10), text, font=face, fill=color)
    return width


def metric(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, value: str, color: str = TEAL) -> None:
    draw.text((x, y), label.upper(), font=font(19, bold=True), fill=MUTED)
    draw.text((x, y + 29), value, font=font(39, bold=True), fill=color)


def scene_01(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 1, dark=True)
    rounded(draw, (90, 315, 332, 557), TEAL, radius=24)
    draw.text((139, 365), "OT", font=font(108, bold=True), fill=WHITE)
    draw.text((400, 324), "OMICS", font=font(91, bold=True), fill=WHITE)
    draw.text((400, 418), "TRUST", font=font(91, bold=True), fill="#77B7AD")
    draw.text((405, 536), "Scientific evidence audit for omics", font=font(31), fill="#C7D4E4")
    pill(draw, (405, 622), "BUILT WITH CODEX", "#183958", "#CBE0FA")
    pill(draw, (665, 622), "GPT-5.6 EVIDENCE COPILOT", "#183958", "#CBE0FA")
    draw.text((91, 866), "Is the signal trustworthy, or is it confounding?", font=font(35, bold=True), fill=WHITE)
    return image


def scene_02(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 2)
    steps = [
        ("SIGNIFICANT", "Clean plot\nsmall p-value", BLUE_LIGHT, BLUE),
        ("HIDDEN RISK", "Batch\nmissing metadata", AMBER_LIGHT, AMBER),
        ("FALSE TRUST", "Costly follow-up\nfragile conclusion", RED_LIGHT, RED),
    ]
    x_positions = [110, 695, 1280]
    for index, ((label, detail, fill, color), x) in enumerate(zip(steps, x_positions)):
        rounded(draw, (x, 345, x + 470, 690), fill, outline=color, radius=18, width=3)
        draw.text((x + 34, 386), label, font=font(27, bold=True), fill=color)
        y = 470
        for line in detail.splitlines():
            draw.text((x + 34, y), line, font=font(39, bold=True), fill=INK)
            y += 58
        if index < 2:
            draw.line((x + 485, 520, x + 565, 520), fill=MUTED, width=5)
            draw.polygon(((x + 565, 520), (x + 535, 504), (x + 535, 536)), fill=MUTED)
    draw.text((110, 776), "A beautiful result can still be scientifically unsafe.", font=font(38, bold=True), fill=INK)
    return image


def scene_03(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 3)
    labels = ["INPUT", "QC", "SIGNAL", "NULL", "RISK", "STABILITY", "TRUST"]
    colors = [NAVY, TEAL, BLUE, BLUE, AMBER, TEAL, RED]
    x = 92
    y = 350
    widths = [205, 180, 210, 180, 190, 245, 220]
    for index, (label, color, box_w) in enumerate(zip(labels, colors, widths)):
        rounded(draw, (x, y, x + box_w, y + 105), WHITE, outline=color, radius=12, width=3)
        draw.text((x + 24, y + 35), label, font=font(26, bold=True), fill=color)
        if index < len(labels) - 1:
            draw.line((x + box_w + 8, y + 52, x + box_w + 46, y + 52), fill=MUTED, width=4)
            draw.polygon(((x + box_w + 46, y + 52), (x + box_w + 28, y + 41), (x + box_w + 28, y + 63)), fill=MUTED)
        x += box_w + 48

    outputs = [
        ("FAILURE HIERARCHY", "What failed first"),
        ("CLAIM MATRIX", "What can be said"),
        ("EVIDENCE LEDGER", "How it can be reproduced"),
        ("HTML / JSON / PDF", "How it can be reviewed"),
    ]
    for index, (heading, detail) in enumerate(outputs):
        bx = 92 + index * 445
        rounded(draw, (bx, 585, bx + 405, 775), WHITE, outline=LINE, radius=12)
        draw.rectangle((bx, 585, bx + 10, 775), fill=TEAL if index < 3 else AMBER)
        draw.text((bx + 35, 625), heading, font=font(24, bold=True), fill=INK)
        draw_wrapped(draw, (bx + 35, 680), detail, font(25), MUTED, 330)
    return image


def scene_04(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 4)
    metric(draw, 100, 332, "Data quality", "PASS")
    metric(draw, 100, 454, "Structural signal", "DETECTED")
    metric(draw, 100, 576, "Stability", "HIGH")
    metric(draw, 420, 332, "Batch risk", "HIGH", RED)
    metric(draw, 420, 454, "Trust", "UNSAFE", RED)
    metric(draw, 420, 576, "Safe to interpret", "NO", RED)
    rounded(draw, (98, 735, 745, 858), RED_LIGHT, outline=RED, radius=12, width=2)
    draw.text((126, 765), "PASS IS NOT TRUST", font=font(30, bold=True), fill=RED)
    draw.text((126, 810), "Interpretation is blocked.", font=font(27), fill=INK)
    framed_asset(image, draw, ASSET_DIR / "audit_report.jpg", (815, 285, 1818, 875))
    return image


def scene_05(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 5)
    framed_asset(image, draw, ASSET_DIR / "evidence_copilot.jpg", (995, 274, 1815, 880))
    items = [
        ("NATURAL LANGUAGE", "Maps the research request to a registered workflow", TEAL),
        ("DETERMINISTIC CORE", "Statistics and safety gates remain authoritative", BLUE),
        ("NO SILENT REROUTING", "Explicit workflows run exactly or return a clear error", AMBER),
        ("LOCAL DATA BOUNDARY", "No raw matrix, patient rows, or local paths sent", RED),
    ]
    y = 302
    for heading, detail, color in items:
        draw.rectangle((95, y, 110, y + 108), fill=color)
        draw.text((138, y + 4), heading, font=font(25, bold=True), fill=color)
        draw_wrapped(draw, (138, y + 43), detail, font(25), INK, 735, 6)
        y += 140
    pill(draw, (100, 850), "CORE WORKS WITHOUT AN API KEY", TEAL_LIGHT, TEAL)
    return image


def scene_06(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 6)
    metric(draw, 100, 304, "Patients", "116")
    metric(draw, 340, 304, "Features", "28,220")
    metric(draw, 650, 304, "Axes screened", "25")
    draw.text((100, 455), "TOP INTERNAL AXIS", font=font(23, bold=True), fill=MUTED)
    draw.text((100, 490), "PC11", font=font(108, bold=True), fill=NAVY)
    rounded(draw, (100, 642, 850, 835), BLUE_LIGHT, outline=BLUE, radius=16, width=2)
    metric(draw, 135, 675, "Odds ratio / 1 SD", "0.1688", BLUE)
    metric(draw, 465, 675, "Wald p", "0.00377", BLUE)
    metric(draw, 665, 675, "FDR", "0.03145", BLUE)
    framed_asset(image, draw, ASSET_DIR / "pc11_evidence.jpg", (965, 273, 1815, 881))
    return image


def scene_07(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 7)
    metric(draw, 95, 310, "Permutation p", "0.003996", BLUE)
    metric(draw, 95, 448, "Bootstrap direction", "99.9%", TEAL)
    metric(draw, 95, 586, "Metadata R-squared", "0.01793", AMBER)
    rounded(draw, (92, 733, 647, 855), AMBER_LIGHT, outline=AMBER, radius=12, width=2)
    draw.text((120, 758), "INTERNAL EVIDENCE", font=font(25, bold=True), fill=AMBER)
    draw.text((120, 803), "Strong, but not external validation", font=font(25), fill=INK)
    report_pages = ["pc11_report_page-04.png", "pc11_report_page-05.png", "pc11_report_page-07.png"]
    positions = [(715, 292, 1048, 874), (1080, 292, 1413, 874), (1445, 292, 1778, 874)]
    for name, box in zip(report_pages, positions):
        framed_asset(image, draw, ASSET_DIR / name, box)
    return image


def scene_08(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 8)
    pill(draw, (95, 285), "IF INDEPENDENTLY REPRODUCED", AMBER_LIGHT, AMBER)
    rounded(draw, (95, 375, 890, 835), WHITE, outline=LINE, radius=14)
    draw.text((135, 415), "PC11 / VASOGATE", font=font(29, bold=True), fill=BLUE)
    pc11_items = [
        "Test molecular modification of vasopressor response",
        "Design sharper, locked sepsis validation studies",
        "Prioritize mechanisms for wet-lab follow-up",
    ]
    y = 490
    for index, item in enumerate(pc11_items, 1):
        rounded(draw, (135, y, 187, y + 52), BLUE_LIGHT, radius=26)
        draw.text((153, y + 10), str(index), font=font(24, bold=True), fill=BLUE)
        draw_wrapped(draw, (215, y + 4), item, font(27), INK, 610, 6)
        y += 102

    rounded(draw, (950, 285, 1818, 835), NAVY, radius=14)
    draw.text((995, 332), "OMICS TRUST LAYER", font=font(29, bold=True), fill="#79B9AF")
    impact_items = [
        ("EARLIER", "Reject misleading signals before expensive validation"),
        ("FASTER", "Move auditable evidence into experiments and review"),
        ("SAFER", "Keep uncertainty visible in every result package"),
    ]
    y = 420
    for heading, detail in impact_items:
        draw.text((995, y), heading, font=font(27, bold=True), fill="#F0C36A")
        draw_wrapped(draw, (995, y + 43), detail, font(27), WHITE, 740, 7)
        y += 132
    return image


def scene_09(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 9)
    draw.text((100, 310), "CAN CLAIM", font=font(27, bold=True), fill=TEAL)
    draw_wrapped(draw, (100, 365), "A stable internal treatment-by-axis interaction hypothesis in the analyzed VANISH cohort.", font(30), INK, 730, 10)
    draw.line((100, 510, 815, 510), fill=LINE, width=2)
    draw.text((100, 555), "CANNOT CLAIM", font=font(27, bold=True), fill=RED)
    cannot = ["Biomarker qualification", "Treatment recommendation", "Causal mechanism", "Clinical use"]
    y = 610
    for item in cannot:
        draw.ellipse((104, y + 10, 118, y + 24), fill=RED)
        draw.text((140, y), item, font=font(29), fill=INK)
        y += 54
    pill(draw, (100, 843), "NEXT: LOCKED INDEPENDENT VALIDATION", TEAL_LIGHT, TEAL)
    framed_asset(image, draw, ASSET_DIR / "pc11_report_page-10.png", (945, 284, 1372, 879))
    framed_asset(image, draw, ASSET_DIR / "pc11_report_page-11.png", (1400, 284, 1827, 879))
    return image


def scene_10(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 10)
    people = [
        (
            "PROF ANTHONY GORDON MBE, FMEDSCI",
            "Chair in Anaesthesia and Critical Care; Head of Division of Anaesthetics, Pain Medicine and Intensive Care; NIHR Senior Investigator",
            "Imperial College London",
        ),
        (
            "PROF TOM VAN DER POLL",
            "Professor of Infectious Diseases",
            "Amsterdam UMC",
        ),
        (
            "DR DAVID ANTCLIFFE",
            "Clinical Associate Professor in Critical Care Medicine",
            "Imperial College London",
        ),
    ]
    y = 286
    for index, (name, role, institution) in enumerate(people):
        color = [TEAL, BLUE, AMBER][index]
        rounded(draw, (100, y, 1818, y + 154), WHITE, outline=LINE, radius=12)
        draw.rectangle((100, y, 114, y + 154), fill=color)
        draw.text((145, y + 25), name, font=font(28, bold=True), fill=INK)
        draw.text((145, y + 72), role, font=font(25), fill=MUTED)
        draw.text((145, y + 111), institution, font=font(23, bold=True), fill=color)
        y += 177
    rounded(draw, (100, 826, 1818, 888), AMBER_LIGHT, outline=AMBER, radius=10)
    draw.text((128, 844), "Scientific review and possible re-analysis discussion are ongoing. No endorsement or validation is implied.", font=font(24, bold=True), fill=AMBER)
    return image


def scene_11(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 11)
    rounded(draw, (95, 285, 1050, 865), NAVY, radius=14)
    draw.text((138, 322), "CODEX BUILD LOG", font=font(25, bold=True, mono=True), fill="#78B8AF")
    lines = [
        "+ workflow registry and explicit routing",
        "+ FastAPI and private web console",
        "+ claim matrix and evidence ledger",
        "+ SSRF, XML, SQL, and release hardening",
        "+ responsive and report asset repairs",
        "+ package-boundary regression tests",
    ]
    y = 390
    for line in lines:
        draw.text((138, y), line, font=font(25, mono=True), fill=WHITE)
        y += 65
    draw.text((138, 795), "$ pytest -q", font=font(25, mono=True), fill="#F0C36A")

    rounded(draw, (1120, 285, 1818, 585), TEAL_LIGHT, outline=TEAL, radius=14, width=3)
    draw.text((1170, 334), "TEST SUITE", font=font(27, bold=True), fill=TEAL)
    draw.text((1170, 405), "119", font=font(104, bold=True), fill=NAVY)
    draw.text((1420, 452), "PASSED", font=font(34, bold=True), fill=TEAL)
    draw.text((1170, 526), "7 intentionally skipped", font=font(26), fill=MUTED)
    rounded(draw, (1120, 620, 1818, 865), WHITE, outline=LINE, radius=14)
    draw.text((1170, 660), "FOCUSED RELEASE", font=font(27, bold=True), fill=INK)
    draw_wrapped(draw, (1170, 715), "OmicsTrust core, Evidence Copilot, PC11 evidence, API, web demo, and reproducible reports.", font(27), MUTED, 585, 8)
    return image


def scene_12(segment: dict) -> Image.Image:
    image, draw = base_slide(segment["title"], segment["caption"], 12, dark=True)
    rounded(draw, (95, 300, 335, 540), TEAL, radius=24)
    draw.text((145, 350), "OT", font=font(106, bold=True), fill=WHITE)
    draw.text((410, 310), "EVIDENCE", font=font(86, bold=True), fill=WHITE)
    draw.text((410, 404), "BEFORE INTERPRETATION", font=font(66, bold=True), fill="#77B7AD")
    draw_wrapped(
        draw,
        (410, 542),
        "Make evidence auditable before a scientific result becomes an expensive decision.",
        font(34),
        "#C7D4E4",
        1240,
        12,
    )
    pill(draw, (410, 704), "RESEARCH USE ONLY", "#183958", "#F0C36A")
    draw.text((410, 790), "Built with Codex and GPT-5.6", font=font(29, bold=True), fill=WHITE)
    return image


SCENE_RENDERERS = [
    scene_01,
    scene_02,
    scene_03,
    scene_04,
    scene_05,
    scene_06,
    scene_07,
    scene_08,
    scene_09,
    scene_10,
    scene_11,
    scene_12,
]


def ffmpeg_duration(ffmpeg: str, media_path: Path) -> float:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(media_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(f"Could not read duration for {media_path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def srt_time(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


class OfflineNarrator:
    """Small offline eSpeak-NG wrapper using the library bundled by piper-tts."""

    def __init__(self) -> None:
        package_dir = Path(piper.__file__).resolve().parent
        library_path = package_dir / "espeakbridge.so"
        if not library_path.exists():
            raise RuntimeError("piper-tts is required for offline narration")

        self.lib = ctypes.CDLL(str(library_path))
        self.samples: list[int] = []
        callback_type = ctypes.CFUNCTYPE(
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_short),
            ctypes.c_int,
            ctypes.c_void_p,
        )

        @callback_type
        def callback(waveform, sample_count, _events):
            if waveform and sample_count:
                self.samples.extend(waveform[index] for index in range(sample_count))
            return 0

        self.callback = callback
        self.lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        self.lib.espeak_Initialize.restype = ctypes.c_int
        self.sample_rate = self.lib.espeak_Initialize(2, 0, str(package_dir).encode(), 0)
        if self.sample_rate <= 0:
            raise RuntimeError("Could not initialize the offline narrator")

        self.lib.espeak_SetSynthCallback.argtypes = [callback_type]
        self.lib.espeak_SetSynthCallback(self.callback)
        self.lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
        if self.lib.espeak_SetVoiceByName(VOICE.encode()) != 0:
            raise RuntimeError(f"Offline voice was not found: {VOICE}")

        self.lib.espeak_SetParameter.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.lib.espeak_SetParameter(1, VOICE_RATE, 0)
        self.lib.espeak_SetParameter(2, 165, 0)
        self.lib.espeak_SetParameter(3, 43, 0)
        self.lib.espeak_SetParameter(4, 42, 0)
        self.lib.espeak_Synth.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.c_void_p,
        ]

    def synthesize(self, text: str, output_path: Path) -> None:
        encoded = text.encode("utf-8")
        self.samples.clear()
        unique_id = ctypes.c_uint(0)
        result = self.lib.espeak_Synth(
            encoded,
            len(encoded) + 1,
            0,
            0,
            0,
            1,
            ctypes.byref(unique_id),
            None,
        )
        if result != 0:
            raise RuntimeError(f"Offline narration failed with code {result}")
        self.lib.espeak_Synchronize()

        pcm = array.array("h", self.samples)
        if sys.byteorder != "little":
            pcm.byteswap()
        with wave.open(str(output_path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(self.sample_rate)
            stream.writeframes(pcm.tobytes())


def build() -> None:
    for directory in (SLIDE_DIR, AUDIO_DIR, CLIP_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    segments = json.loads(SEGMENTS_PATH.read_text(encoding="utf-8"))
    if len(segments) != len(SCENE_RENDERERS):
        raise RuntimeError("Narration and scene renderer counts do not match")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    narrator = OfflineNarrator()

    clips: list[Path] = []
    caption_entries: list[str] = []
    timeline = 0.0

    for index, (segment, renderer) in enumerate(zip(segments, SCENE_RENDERERS), start=1):
        slide_path = SLIDE_DIR / f"{segment['id']}.png"
        narration_path = AUDIO_DIR / f"{segment['id']}.txt"
        audio_path = AUDIO_DIR / f"{segment['id']}.wav"
        clip_path = CLIP_DIR / f"{segment['id']}.mp4"

        renderer(segment).save(slide_path, quality=95)
        narration_path.write_text(segment["narration"] + "\n", encoding="utf-8")
        narrator.synthesize(segment["narration"], audio_path)

        audio_duration = ffmpeg_duration(ffmpeg, audio_path)
        clip_duration = audio_duration + 0.55
        fade_out_start = max(0.0, clip_duration - 0.35)
        audio_fade_start = max(0.0, audio_duration - 0.12)
        filter_graph = (
            f"[0:v]scale={WIDTH}:{HEIGHT},"
            f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out_start:.3f}:d=0.35,"
            "format=yuv420p[v];"
            f"[1:a]highpass=f=75,lowpass=f=8500,"
            f"acompressor=threshold=0.125:ratio=2:attack=20:release=250,"
            f"afade=t=in:st=0:d=0.04,afade=t=out:st={audio_fade_start:.3f}:d=0.12,"
            "apad=pad_dur=0.55[a]"
        )
        run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-framerate",
                str(FPS),
                "-i",
                str(slide_path),
                "-i",
                str(audio_path),
                "-filter_complex",
                filter_graph,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-t",
                f"{clip_duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-r",
                str(FPS),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(clip_path),
            ]
        )
        clips.append(clip_path)
        caption_entries.append(
            f"{index}\n{srt_time(timeline + 0.05)} --> {srt_time(timeline + audio_duration)}\n"
            f"{segment['narration']}\n"
        )
        timeline += clip_duration

    if timeline > 180:
        raise RuntimeError(f"Rendered timeline is {timeline:.2f}s, over the three-minute limit")

    concat_path = CLIP_DIR / "concat.txt"
    concat_path.write_text("".join(f"file '{path.resolve()}'\n" for path in clips), encoding="utf-8")
    captions_path = VIDEO_DIR / "captions.srt"
    captions_path.write_text("\n".join(caption_entries), encoding="utf-8")

    run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            "-metadata",
            "title=OmicsTrust: Evidence Before Interpretation",
            "-metadata",
            "comment=OpenAI Build Week demo. Research Use Only.",
            "-movflags",
            "+faststart",
            str(FINAL_VIDEO),
        ]
    )

    final_duration = ffmpeg_duration(ffmpeg, FINAL_VIDEO)
    print(f"Built: {FINAL_VIDEO}")
    print(f"Duration: {final_duration:.2f} seconds")
    print(f"Captions: {captions_path}")


if __name__ == "__main__":
    build()
