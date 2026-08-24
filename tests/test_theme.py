import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import tomllib
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THEME = {
    "background": "#040404",
    "foreground": "#feffff",
    "accent": "#5da602",
    "border": "#355f01",
    "regular_border": "#141414",
    "bar": "#000000",
    "muted": "#777b80",
    "chromium": "21,21,21",
    "ghostty_background": "#040404",
    "ghostty_palette": (
        "0=#040404", "1=#d84a33", "2=#5da602", "3=#eebb6e",
        "4=#417ab3", "5=#e5c499", "6=#bdcfe5", "7=#dbded8",
        "8=#685656", "9=#d76b42", "10=#99b52c", "11=#ffb670",
        "12=#97d7ef", "13=#aa7900", "14=#bdcfe5", "15=#e4d5c7",
    ),
    "ghostty_selection": "#303030",
    "ghostty_cursor_text": "#000000",
    "btop_box": "#282828",
}

COLOR_KEYS = {
    "mode", "accent", "selection", "muted", "background", "dark_background",
    "darker_background", "lighter_background", "foreground", "dark_foreground",
    "light_foreground", "bright_foreground", "red", "yellow", "orange", "green",
    "cyan", "blue", "magenta", "brown", "bright_red", "bright_yellow",
    "bright_green", "bright_cyan", "bright_blue", "bright_magenta",
}


def load_palette():
    with (ROOT / "colors.toml").open("rb") as handle:
        return tomllib.load(handle)


def luminance(color):
    values = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    values = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def png_pixels(path):
    data = path.read_bytes()
    position = 8
    compressed = bytearray()
    width = height = None
    while position < len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        payload = data[position + 8:position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        elif kind == b"IDAT":
            compressed.extend(payload)
    rows = zlib.decompress(compressed)
    stride = 1 + width * 3
    return [rows[offset + 1:offset + stride] for offset in range(0, height * stride, stride)]


class ThemeTests(unittest.TestCase):
    def test_adventure_btop_has_complete_subdued_chrome(self):
        content = (ROOT / "btop.theme").read_text()
        roles = dict(re.findall(r'theme\[([^]]+)\]="([^"]*)"', content))
        self.assertEqual(50, len(roles))
        for role in ("cpu_box", "mem_box", "net_box", "proc_box"):
            self.assertEqual(THEME["btop_box"], roles[role])
        self.assertEqual("#777b80", roles["graph_text"])
        self.assertEqual("#171717", roles["meter_bg"])
        self.assertEqual("#41b3a9", roles["process_start"])
        self.assertEqual("#417ab3", roles["process_mid"])
        self.assertEqual("#882252", roles["process_end"])

    def test_palettes_preserve_source_identity_and_are_readable(self):
        palette = load_palette()
        self.assertEqual(COLOR_KEYS, set(palette))
        self.assertEqual("dark", palette["mode"])
        for role in ("background", "foreground", "accent", "muted"):
            self.assertEqual(THEME[role].lower(), palette[role].lower())
        self.assertGreaterEqual(contrast(palette["foreground"], palette["background"]), 4.5)
        self.assertGreaterEqual(contrast(palette["muted"], palette["background"]), 4.5)

    def test_integrations_preserve_focus_color(self):
        required = {
            "hyprland.lua", "shell.hyprland.toml", "btop.theme", "chromium.theme",
            "icons.theme",
        }
        self.assertTrue(required <= {path.name for path in ROOT.iterdir()})
        self.assertEqual(THEME["chromium"], (ROOT / "chromium.theme").read_text().strip())
        shell = tomllib.loads((ROOT / "shell.hyprland.toml").read_text())
        self.assertEqual(THEME["border"].lower(), shell["active-border"].lower())
        self.assertEqual(
            THEME["regular_border"].lower(),
            shell["active-border-foreground"].lower(),
        )
        self.assertIn(THEME["border"].removeprefix("#").lower(), (ROOT / "hyprland.lua").read_text().lower())

    def test_zed_uses_adventure_palette_and_background(self):
        path = ROOT / "zed.json"
        self.assertTrue(path.is_file(), "theme is missing zed.json")
        zed = json.loads(path.read_text())
        self.assertEqual("Adventure", zed["name"])
        self.assertEqual(1, len(zed["themes"]))
        theme = zed["themes"][0]
        self.assertEqual("Adventure", theme["name"])
        self.assertEqual("dark", theme["appearance"])
        style = theme["style"]
        for role in (
            "background", "editor.background", "panel.background",
            "surface.background", "title_bar.background", "status_bar.background",
            "editor.subheader.background", "terminal.background", "terminal.ansi.background",
        ):
            self.assertIn(role, style)
            self.assertEqual("#040404", style[role])
        expected_ansi = {
            "black": "#040404", "red": "#d84a33", "green": "#5da602",
            "yellow": "#eebb6e", "blue": "#417ab3", "magenta": "#e5c499",
            "cyan": "#bdcfe5", "white": "#dbded8", "bright_black": "#685656",
            "bright_red": "#d76b42", "bright_green": "#99b52c",
            "bright_yellow": "#ffb670", "bright_blue": "#97d7ef",
            "bright_magenta": "#aa7900", "bright_cyan": "#bdcfe5",
            "bright_white": "#e4d5c7",
        }
        for name, color in expected_ansi.items():
            self.assertEqual(color, style[f"terminal.ansi.{name}"])

    def test_assets_have_expected_dimensions(self):
        for relative, expected in {
            "backgrounds/adventure.png": (1920, 1080),
            "unlock.png": (1920, 1080),
            "preview.png": (640, 360),
            "preview-unlock.png": (640, 360),
        }.items():
            with self.subTest(relative=relative):
                data = (ROOT / relative).read_bytes()
                self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
                self.assertEqual(expected, struct.unpack(">II", data[16:24]))

    def test_desktop_login_and_lock_assets_use_theme_background(self):
        expected_pixel = bytes.fromhex("040404")
        for relative in (
            "backgrounds/adventure.png",
            "unlock.png",
            "preview.png",
            "preview-unlock.png",
        ):
            with self.subTest(relative=relative):
                rows = png_pixels(ROOT / relative)
                self.assertTrue(all(
                    row[offset:offset + 3] == expected_pixel
                    for row in rows
                    for offset in range(0, len(row), 3)
                ))

    def test_installer_overwrites_only_adventure(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "themes"
            first = subprocess.run(
                ["bash", ROOT / "install.sh", "--destination", destination],
                capture_output=True, text=True, env=os.environ | {"PATH": "/usr/bin"},
            )
            self.assertEqual(0, first.returncode, first.stderr)
            marker = destination / "adventure" / "stale"
            marker.write_text("stale")
            second = subprocess.run(
                ["bash", ROOT / "install.sh", "--destination", destination],
                capture_output=True, text=True, env=os.environ | {"PATH": "/usr/bin"},
            )
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertFalse(marker.exists())
            self.assertTrue((destination / "adventure" / "colors.toml").is_file())
            self.assertTrue((destination / "adventure" / "zed.json").is_file())
            self.assertEqual(["adventure"], [path.name for path in destination.iterdir()])

    def test_installer_activates_adventure(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            destination = temporary / "themes"
            binary_directory = temporary / "bin"
            activation_log = temporary / "activation.log"
            binary_directory.mkdir()
            omarchy = binary_directory / "omarchy"
            omarchy.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" > "$ACTIVATION_LOG"\n')
            omarchy.chmod(0o755)
            env = os.environ | {
                "ACTIVATION_LOG": str(activation_log),
                "PATH": f"{binary_directory}:{os.environ['PATH']}",
            }

            result = subprocess.run(
                ["bash", ROOT / "install.sh", "--destination", destination],
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(activation_log.exists(), "installer did not invoke omarchy")
            self.assertEqual("theme set adventure\n", activation_log.read_text())

    @unittest.skipUnless(shutil.which("omarchy-theme-set"), "Omarchy is not installed")
    def test_current_omarchy_generates_theme(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            themes = home / ".config/omarchy/themes"
            runtime = home / "run"
            themes.mkdir(parents=True)
            runtime.mkdir()
            shutil.copytree(
                ROOT,
                themes / "adventure",
                ignore=shutil.ignore_patterns(".git", "tests"),
            )
            env = os.environ | {
                "HOME": str(home), "OMARCHY_PATH": "/usr/share/omarchy",
                "OMARCHY_THEME_HEADLESS": "1", "XDG_RUNTIME_DIR": str(runtime),
            }
            result = subprocess.run(
                ["omarchy-theme-set", "adventure"],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            generated = home / ".local/state/omarchy/current/theme"
            self.assertIn(THEME["background"], (generated / "colors.toml").read_text())
            ghostty = (generated / "ghostty.conf").read_text()
            self.assertIn(
                f'background = {THEME.get("ghostty_background", THEME["background"])}',
                ghostty,
            )
            self.assertIn(f'foreground = {THEME["foreground"]}', ghostty)
            for entry in THEME["ghostty_palette"]:
                self.assertIn(f"palette = {entry}", ghostty)
            self.assertIn(
                f'selection-background = {THEME["ghostty_selection"]}', ghostty
            )
            if "ghostty_cursor_text" in THEME:
                self.assertIn(
                    f'cursor-text = {THEME["ghostty_cursor_text"]}', ghostty
                )

            shell = tomllib.loads((generated / "shell.toml").read_text())
            self.assertEqual(THEME["border"].lower(), shell["hyprland"]["active-border"].lower())
            self.assertEqual(
                THEME["regular_border"].lower(),
                shell["hyprland"]["active-border-foreground"].lower(),
            )
            self.assertEqual(THEME["bar"].lower(), shell["bar"]["background"].lower())


if __name__ == "__main__":
    unittest.main()
