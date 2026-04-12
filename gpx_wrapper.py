from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_NOZZLE_TEMP = "200"
START_MARKER = "GPX_START_MARKER"
END_MARKER = "GPX_END_MARKER"
BANNER_LINES = (
    "GPX Wrapper for MakerBot Replicator 2",
    "This script injects necessary Start G-code for the Replicator 2",
)
TEMP_PATTERN = re.compile(r"^M10[49]\s+S(?P<temp>\d+)", re.IGNORECASE)


class GpxWrapperError(Exception):
    pass


def read_ascii_lines(path: Path) -> list[str]:
    return path.read_text(encoding="ascii", errors="ignore").splitlines()


def build_injected_block(nozzle_temp: str) -> list[str]:
    return [
        "; --- GPX_START_MARKER ---",
        "; ====== START GCODE FOR MAKERBOT REPLICATOR 2 ======",
        "",
        "; --- Full homing using endstops ---",
        "G162 X Y F3000        ; Home XY to MAX endstops (rear/right)",
        "G161 Z F1200          ; Home Z to MIN endstop (platform up)",
        "",
        "; --- Origin consistent with MAX homing ---",
        "G92 X285 Y152 Z0      ; R2: X=285, Y=152",
        "",
        "G1 Z5 F1200           ; Raise a bit to avoid contact",
        "",
        "; --- Nozzle heating ---",
        f"M104 S{nozzle_temp}",
        "M6 T0                 ; Wait for nozzle to heat",
        "",
        "; --- Extruder preparation ---",
        "G92 E0                ; Reset extrusion",
        "",
        "; ====== PURGE LINE ======",
        "G1 X5 Y5 Z0.3 F3000   ; Move to front-left corner",
        "G1 E8 F200            ; Extrude a bit",
        "G1 X120 Y5 F1500      ; Draw purge line",
        "G92 E0                ; Reset extrusion",
        "; ====== END PURGE LINE ======",
        "",
        "; --- GPX_END_MARKER ---",
    ]

def inject_gpx_block(path: Path, nozzle_temp: str = DEFAULT_NOZZLE_TEMP) -> int:
    lines = read_ascii_lines(path)

    start_index = next((index for index, line in enumerate(lines) if START_MARKER in line), -1)
    if start_index < 0:
        return 10

    end_index = next((index for index in range(start_index + 1, len(lines)) if END_MARKER in lines[index]), -1)
    if end_index < 0:
        return 11

    new_lines: list[str] = []
    if start_index > 0:
        new_lines.extend(lines[:start_index])

    new_lines.extend(build_injected_block(nozzle_temp))

    if end_index + 1 <= len(lines) - 1:
        new_lines.extend(lines[end_index + 1 :])

    path.write_text("\r\n".join(new_lines) + "\r\n", encoding="ascii")
    return 0


def get_runtime_dir(base_dir: Path) -> Path:
    msys_runtime = Path(r"C:\msys64\ucrt64\bin")
    if (msys_runtime / "libiconv-2.dll").exists():
        return msys_runtime
    return base_dir


def build_runtime_env(base_dir: Path) -> dict[str, str]:
    runtime_dir = get_runtime_dir(base_dir)
    env = os.environ.copy()
    env["PATH"] = f"{runtime_dir}{os.pathsep}{env.get('PATH', '')}"
    return env


def extract_first_layer_temp(path: Path, default_temp: str = DEFAULT_NOZZLE_TEMP) -> str:
    for line in read_ascii_lines(path):
        match = TEMP_PATTERN.match(line)
        if match:
            return match.group("temp")
    return default_temp


def get_prusa_gcode_path(input_path: Path) -> Path | None:
    if re.search(r"(?i)\.gcode\.pp$", str(input_path)):
        return Path(re.sub(r"(?i)\.pp$", "", str(input_path)))
    return None


def convert_with_gpx(gpx_exe: Path, input_path: Path, output_path: Path, env: dict[str, str]) -> None:
    process = subprocess.run(
        [str(gpx_exe), "-m", "r2", str(input_path), str(output_path)],
        env=env,
        check=False,
    )
    if process.returncode != 0:
        raise GpxWrapperError("GPX failed during conversion.")
    if not output_path.exists():
        raise GpxWrapperError("GPX did not generate the .x3g file")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", nargs="?", help="Path to the .gcode.pp file to process")
    parser.add_argument("--input-path", dest="input_path_flag", help="Path to the .gcode.pp file to process")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    for line in BANNER_LINES:
        print(line)

    args = parse_args(argv)
    input_path_value = args.input_path_flag or args.input_path
    if not input_path_value:
        print("ERROR: Missing input path argument.")
        print()
        return 1

    input_path = Path(input_path_value)
    base_dir = Path(__file__).resolve().parent
    gpx_exe = base_dir / "gpx.exe"
    env = build_runtime_env(base_dir)
    prusa_gcode_path = get_prusa_gcode_path(input_path)
    already_converted = False

    with tempfile.NamedTemporaryFile(prefix="gpxwrap_", suffix=".x3g", delete=False) as temp_file:
        intermediate_x3g = Path(temp_file.name)

    try:
        if not input_path.exists():
            raise GpxWrapperError(f"Input file does not exist: {input_path}")

        if not gpx_exe.exists():
            raise GpxWrapperError(f"Unable to find GPX: {gpx_exe}")

        first_layer_temp = extract_first_layer_temp(input_path, DEFAULT_NOZZLE_TEMP)
        inject_status = inject_gpx_block(input_path, first_layer_temp)

        if inject_status in (10, 11):
            already_converted = True

        if inject_status != 0 and not already_converted:
            raise GpxWrapperError(f"Unable to inject Start G-code into: {input_path}")

        if already_converted:
            print("GPX markers not found; file may already be converted. Injection skipped.")
            print()
        else:
            convert_with_gpx(gpx_exe, input_path, intermediate_x3g, env)
            shutil.copyfile(intermediate_x3g, input_path)
            if not input_path.exists():
                raise GpxWrapperError(f"Unable to replace content of: {input_path}")

        if prusa_gcode_path is not None:
            input_full_path = input_path.resolve()
            gcode_full_path = prusa_gcode_path.resolve(strict=False)
            if input_full_path != gcode_full_path and prusa_gcode_path.exists():
                prusa_gcode_path.unlink(missing_ok=True)

        print(f"Source file replaced with X3G binary: {input_path}")
        return 0
    except GpxWrapperError as error:
        print(f"ERROR: {error}")
        print()
        return 1
    finally:
        intermediate_x3g.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
