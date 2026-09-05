"""Render a deterministic vertical Ledgerly product demo without external assets."""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path


WIDTH, HEIGHT = 1080, 1920
FPS, SECONDS = 24, 8
OUTPUT = Path("attached_assets/generated_videos/ledgerly-recurring-spend-demo.mp4")


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def ease(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def fade_in(t: float, start: float, duration: float = 0.45) -> float:
    return ease((t - start) / duration)


def fade_out(t: float, start: float, duration: float = 0.45) -> float:
    return 1 - ease((t - start) / duration)


def esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def text(
    value: str,
    x: float,
    y: float,
    size: float,
    color: str,
    *,
    weight: int = 400,
    family: str = "DejaVu Sans",
    anchor: str = "start",
    opacity: float = 1,
    letter_spacing: float = 0,
) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" opacity="{opacity:.3f}" '
        f'font-family="{family}" font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}" letter-spacing="{letter_spacing}px">{esc(value)}</text>'
    )


def rect(
    x: float,
    y: float,
    width: float,
    height: float,
    fill: str,
    *,
    radius: float = 0,
    stroke: str = "none",
    stroke_width: float = 1,
    opacity: float = 1,
) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" opacity="{opacity:.3f}"/>'
    )


def svg_frame(t: float) -> str:
    paper = "#f6f5f0"
    ink = "#18211e"
    muted = "#77807b"
    line = "#dcded7"
    green = "#4b6659"
    green_dark = "#30483e"
    mint = "#dce8dd"
    orange = "#e57545"
    white = "#fffefa"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        rect(0, 0, WIDTH, HEIGHT, paper),
        # fine editorial grid lines
        rect(70, 104, 940, 1, line),
        rect(70, 1812, 940, 1, line),
    ]

    logo_opacity = fade_in(t, 0.15) * fade_out(t, 7.35)
    parts.extend(
        [
            f'<circle cx="90" cy="72" r="18" fill="{green}" opacity="{logo_opacity:.3f}"/>',
            text("↗", 90, 80, 22, paper, weight=700, anchor="middle", opacity=logo_opacity),
            text("ledgerly", 120, 79, 26, ink, weight=700, opacity=logo_opacity),
            text("PRIVATE BY DESIGN", 1005, 77, 12, muted, family="DejaVu Sans Mono", anchor="end", opacity=logo_opacity, letter_spacing=2),
        ]
    )

    # Intro: quiet editorial title card.
    intro = fade_in(t, 0.35) * fade_out(t, 2.0)
    intro_y = 580 - (ease((t - 0.35) / 1.2) * 36)
    parts.extend(
        [
            text("RECURRING SPEND INTELLIGENCE", 90, 380, 14, green, family="DejaVu Sans Mono", opacity=intro, letter_spacing=2),
            rect(90, 402, 52, 2, green, opacity=intro),
            text("Find the quiet", 90, intro_y, 68, ink, family="DejaVu Serif", weight=700, opacity=intro, letter_spacing=-2),
            text("leaks", 90, intro_y + 82, 76, orange, family="DejaVu Serif", weight=700, opacity=intro, letter_spacing=-2),
            text("in your money.", 300, intro_y + 82, 68, ink, family="DejaVu Serif", weight=700, opacity=intro, letter_spacing=-2),
            text("A clearer picture of the charges that quietly repeat.", 90, intro_y + 160, 21, muted, opacity=intro),
        ]
    )

    # Input scene: transactions arrive into Ledgerly.
    input_opacity = fade_in(t, 1.85, 0.5) * fade_out(t, 4.25, 0.45)
    input_y = 310 + (1 - ease((t - 1.85) / 0.8)) * 35
    parts.extend(
        [
            text("01 / INPUT", 90, input_y, 13, green, family="DejaVu Sans Mono", opacity=input_opacity, letter_spacing=2),
            text("Bring your transactions", 90, input_y + 58, 34, ink, weight=700, opacity=input_opacity),
            rect(90, input_y + 92, 900, 170, mint, radius=4, stroke="#b8c9b7", opacity=input_opacity),
            rect(455, input_y + 125, 170, 48, green, radius=24, opacity=input_opacity),
            text("↑", 490, input_y + 157, 24, paper, weight=700, anchor="middle", opacity=input_opacity),
            text("Upload a CSV", 535, input_y + 155, 15, paper, weight=700, anchor="middle", opacity=input_opacity),
            text("or paste transaction JSON", 540, input_y + 208, 14, muted, anchor="middle", opacity=input_opacity),
        ]
    )

    transactions = [
        ("NETFLIX.COM", "$15.49", "#b86f54"),
        ("SPOTIFY USA", "$11.99", "#73927a"),
        ("PLANET FITNESS", "$24.99", "#8a7b9a"),
        ("COFFEE & MORE", "$6.75", "#ad9161"),
    ]
    for index, (merchant, amount, avatar) in enumerate(transactions):
        row_start = 3.0 + index * 0.18
        row_opacity = input_opacity * fade_in(t, row_start, 0.3)
        y = input_y + 320 + index * 78
        slide = (1 - ease((t - row_start) / 0.45)) * 40
        parts.extend(
            [
                rect(90 + slide, y, 900, 62, white, radius=3, stroke=line, opacity=row_opacity),
                f'<circle cx="{130 + slide}" cy="{y + 31}" r="17" fill="{avatar}" opacity="{row_opacity:.3f}"/>',
                text(merchant, 165 + slide, y + 37, 16, ink, weight=700, opacity=row_opacity),
                text("2026-0" + str(index + 1) + "-05", 600 + slide, y + 36, 13, muted, family="DejaVu Sans Mono", opacity=row_opacity),
                text(amount, 950 + slide, y + 37, 16, ink, weight=700, anchor="end", opacity=row_opacity),
            ]
        )

    # Analysis scene: recognizable pattern scanning.
    analysis = fade_in(t, 3.8, 0.4) * fade_out(t, 5.55, 0.45)
    pulse = 0.5 + 0.5 * math.sin(t * 10)
    parts.extend(
        [
            text("PROCESSING PATTERNS", 90, 400, 13, green, family="DejaVu Sans Mono", opacity=analysis, letter_spacing=2),
            text("Comparing merchants, amounts,", 90, 485, 38, ink, family="DejaVu Serif", weight=700, opacity=analysis),
            text("and intervals.", 90, 535, 38, orange, family="DejaVu Serif", weight=700, opacity=analysis),
            rect(90, 610, 900, 2, line, opacity=analysis),
        ]
    )
    for index in range(4):
        y = 720 + index * 130
        progress = clamp((t - 4.0 - index * 0.12) / 0.75)
        parts.extend(
            [
                rect(90, y, 900, 70, white, radius=3, stroke=line, opacity=analysis),
                text(["merchant", "amount", "monthly", "confidence"][index].upper(), 120, y + 43, 13, muted, family="DejaVu Sans Mono", opacity=analysis, letter_spacing=1),
                rect(400, y + 28, 400, 14, "#edf1eb", radius=7, opacity=analysis),
                rect(400, y + 28, 400 * ease(progress), 14, green, radius=7, opacity=analysis),
                text(["NETFLIX", "$15.49", "30 days", "91%"][index], 940, y + 44, 17, ink, weight=700, anchor="end", opacity=analysis),
            ]
        )
    parts.append(f'<circle cx="540" cy="1300" r="{32 + pulse * 6:.1f}" fill="none" stroke="{orange}" stroke-width="3" opacity="{analysis * (0.45 + pulse * 0.3):.3f}"/>')
    parts.append(text("pattern found", 540, 1307, 14, green, weight=700, anchor="middle", opacity=analysis))

    # Results scene: main payoff.
    results = fade_in(t, 5.05, 0.5) * fade_out(t, 7.6, 0.5)
    results_y = 240 + (1 - ease((t - 5.05) / 0.8)) * 30
    parts.extend(
        [
            text("02 / RESULTS", 90, results_y, 13, green, family="DejaVu Sans Mono", opacity=results, letter_spacing=2),
            text("Your recurring spend", 90, results_y + 58, 39, ink, weight=700, opacity=results),
            text("Annual recurring", 90, results_y + 115, 13, muted, family="DejaVu Sans Mono", opacity=results, letter_spacing=1),
            text("$1,013", 90, results_y + 180, 64, ink, family="DejaVu Serif", weight=700, opacity=results),
            text("estimated / year", 90, results_y + 214, 14, orange, opacity=results),
        ]
    )
    cards = [
        ("$84", "monthly average", white),
        ("4", "subscriptions", mint),
        ("91%", "strongest match", white),
    ]
    for index, (value, label, fill) in enumerate(cards):
        x = 90 + index * 300
        parts.extend(
            [
                rect(x, results_y + 270, 270, 118, fill, radius=3, stroke=line, opacity=results),
                text(value, x + 20, results_y + 322, 32, ink, family="DejaVu Serif", weight=700, opacity=results),
                text(label, x + 20, results_y + 360, 12, muted, family="DejaVu Sans Mono", opacity=results),
            ]
        )
    result_rows = [
        ("N", "Netflix", "$185 / yr", 0.91),
        ("S", "Spotify", "$144 / yr", 0.89),
        ("P", "Planet Fitness", "$300 / yr", 0.96),
    ]
    for index, (initial, merchant, annual, confidence) in enumerate(result_rows):
        y = results_y + 455 + index * 86
        row_opacity = results * fade_in(t, 5.5 + index * 0.12, 0.35)
        parts.extend(
            [
                rect(90, y, 900, 68, white, radius=3, stroke=line, opacity=row_opacity),
                f'<circle cx="128" cy="{y + 34}" r="18" fill="{green}" opacity="{row_opacity:.3f}"/>',
                text(initial, 128, y + 40, 15, paper, weight=700, anchor="middle", opacity=row_opacity),
                text(merchant, 170, y + 40, 17, ink, weight=700, opacity=row_opacity),
                text(f"{round(confidence * 100)}% match", 570, y + 40, 12, green, family="DejaVu Sans Mono", opacity=row_opacity),
                text(annual, 950, y + 40, 17, orange, weight=700, anchor="end", opacity=row_opacity),
            ]
        )

    # Closing card.
    close = fade_in(t, 6.9, 0.55)
    parts.extend(
        [
            rect(90, 1580, 900, 120, green_dark, radius=4, opacity=close),
            text("See what repeats.", 120, 1650, 28, paper, family="DejaVu Serif", weight=700, opacity=close),
            text("ledgerly", 960, 1650, 20, mint, weight=700, anchor="end", opacity=close),
            text("LOCAL ANALYSIS · EVERYDAY MONEY", 90, 1770, 12, muted, family="DejaVu Sans Mono", opacity=close, letter_spacing=2),
        ]
    )
    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    frame_dir = Path(tempfile.mkdtemp(prefix="ledgerly-video-"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        total_frames = FPS * SECONDS
        for frame_number in range(total_frames):
            timestamp = frame_number / FPS
            svg_path = frame_dir / f"frame_{frame_number:04d}.svg"
            png_path = frame_dir / f"frame_{frame_number:04d}.png"
            svg_path.write_text(svg_frame(timestamp), encoding="utf-8")
            subprocess.run(
                ["magick", "-background", "#f6f5f0", str(svg_path), str(png_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            svg_path.unlink()

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                str(frame_dir / "frame_%04d.png"),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(OUTPUT),
            ],
            check=True,
        )
        print(f"Rendered {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)


if __name__ == "__main__":
    main()