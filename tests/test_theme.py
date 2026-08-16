import os
import shutil
import struct
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {
    "adventure": {
        "background": "#040404",
        "foreground": "#feffff",
        "accent": "#5da602",
        "muted": "#777b80",
        "chromium": "4,4,4",
    },
    "adventure-time": {
        "background": "#1f1d45",
        "foreground": "#f8dcc0",
        "accent": "#549235",
        "muted": "#9E9E9E",
        "chromium": "31,29,69",
    },
}

COLOR_KEYS = {
    "mode", "accent", "selection", "muted", "background", "dark_background",
    "darker_background", "lighter_background", "foreground", "dark_foreground",
    "light_foreground", "bright_foreground", "red", "yellow", "orange", "green",
    "cyan", "blue", "magenta", "brown", "bright_red", "bright_yellow",
    "bright_green", "bright_cyan", "bright_blue", "bright_magenta",
}


def load_palette(name):
    with (ROOT / name / "colors.toml").open("rb") as handle:
        return tomllib.load(handle)


def luminance(color):
    values = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    values = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values]
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def contrast(first, second):
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ThemeTests(unittest.TestCase):
    def test_palettes_preserve_source_identity_and_are_readable(self):
        for name, expected in VARIANTS.items():
            with self.subTest(name=name):
                palette = load_palette(name)
                self.assertEqual(COLOR_KEYS, set(palette))
                self.assertEqual("dark", palette["mode"])
                for role in ("background", "foreground", "accent", "muted"):
                    self.assertEqual(expected[role].lower(), palette[role].lower())
                self.assertGreaterEqual(contrast(palette["foreground"], palette["background"]), 4.5)
                self.assertGreaterEqual(contrast(palette["muted"], palette["background"]), 4.5)

    def test_integrations_preserve_focus_color(self):
        for name, expected in VARIANTS.items():
            with self.subTest(name=name):
                required = {
                    "hyprland.lua", "shell.hyprland.toml", "btop.theme", "chromium.theme",
                    "icons.theme",
                }
                self.assertTrue(required <= {path.name for path in (ROOT / name).iterdir()})
                self.assertEqual(expected["chromium"], (ROOT / name / "chromium.theme").read_text().strip())
                shell = tomllib.loads((ROOT / name / "shell.hyprland.toml").read_text())
                self.assertEqual(expected["accent"].lower(), shell["active-border"].lower())
                self.assertIn(expected["accent"].removeprefix("#").lower(), (ROOT / name / "hyprland.lua").read_text().lower())

    def test_assets_have_expected_dimensions(self):
        for name in VARIANTS:
            for relative, expected in {
                f"backgrounds/{name}.png": (1920, 1080),
                "unlock.png": (1920, 1080),
                "preview.png": (640, 360),
                "preview-unlock.png": (640, 360),
            }.items():
                with self.subTest(name=name, relative=relative):
                    data = (ROOT / name / relative).read_bytes()
                    self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
                    self.assertEqual(expected, struct.unpack(">II", data[16:24]))

    def test_installer_overwrites_both_variants_without_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "themes"
            first = subprocess.run(
                ["bash", ROOT / "install.sh", "--destination", destination],
                capture_output=True, text=True,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            marker = destination / "adventure" / "stale"
            marker.write_text("stale")
            second = subprocess.run(
                ["bash", ROOT / "install.sh", "--destination", destination],
                capture_output=True, text=True,
            )
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertFalse(marker.exists())
            for name in VARIANTS:
                self.assertTrue((destination / name / "colors.toml").is_file())

    @unittest.skipUnless(shutil.which("omarchy-theme-set"), "Omarchy is not installed")
    def test_current_omarchy_generates_both_variants(self):
        for name, expected in VARIANTS.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                themes = home / ".config/omarchy/themes"
                runtime = home / "run"
                themes.mkdir(parents=True)
                runtime.mkdir()
                shutil.copytree(ROOT / name, themes / name)
                env = os.environ | {
                    "HOME": str(home), "OMARCHY_PATH": "/usr/share/omarchy",
                    "OMARCHY_THEME_HEADLESS": "1", "XDG_RUNTIME_DIR": str(runtime),
                }
                result = subprocess.run(["omarchy-theme-set", name], capture_output=True, text=True, env=env)
                self.assertEqual(0, result.returncode, result.stderr)
                generated = home / ".local/state/omarchy/current/theme"
                self.assertIn(expected["background"], (generated / "colors.toml").read_text())
                shell = tomllib.loads((generated / "shell.toml").read_text())
                self.assertEqual(expected["accent"].lower(), shell["hyprland"]["active-border"].lower())


if __name__ == "__main__":
    unittest.main()
