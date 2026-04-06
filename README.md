# GPX Wrapper for MakerBot Replicator 2

A PowerShell post-processing script for [PrusaSlicer](https://www.prusa3d.com/en/page/prusaslicer_en/) that automatically injects MakerBot Replicator 2-specific Start G-code and converts sliced G-code to Sailfish X3G binary format.

> This wrapper is designed only for the **MakerBot Replicator 2**. It is not intended for other MakerBot models, even if this repository also contains additional GPX machine configuration files.

## Overview

This wrapper script bridges PrusaSlicer and the GPX converter tool. It:

- **Injects custom Start G-code** optimized for MakerBot Replicator 2 (homing, heating, purge line)
- **Converts G-code to X3G format** using the GPX binary
- **Manages file outputs** automatically (replaces `.gcode.pp` with X3G binary, removes temporary files)
- **Extracts nozzle temperature** from G-code to apply in Start sequence
- **Runs non-interactively** for seamless PrusaSlicer integration

The wrapper logic in `gpx_wrapper.ps1` is currently tailored specifically to the **MakerBot Replicator 2** startup sequence and coordinates.

## Features

- ✅ Marker-based G-code injection (safe, repeatable block replacement)
- ✅ Temperature extraction from first `M104`/`M109` command
- ✅ Automatic removal of PrusaSlicer-generated `.gcode` files
- ✅ Graceful handling of already-converted files
- ✅ Full homing sequence using Sailfish endstop commands
- ✅ Optimized purge line for reliable first layer

## Installation

1. **Clone or download this repository** to your local machine
2. **Ensure GPX binary is present** in the same directory as `gpx_wrapper.ps1`
3. **Configure PrusaSlicer post-processing** (see Usage section below)

### PrusaSlicer Integration

1. Open **PrusaSlicer** → Preferences
2. Navigate to the **Printer** tab
3. Under **G-code substitutions** or **Post-processing scripts**, add:
   ```
   "<PATH_TO_POWERSHELL>\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "<PATH_TO_GPX_WRAPPER>\gpx_wrapper.ps1""
   ```

   **Note**: Replace:
   - `<PATH_TO_POWERSHELL>` with the PowerShell executable path (typically `C:\Windows\System32\WindowsPowerShell\v1.0`)
   - `<PATH_TO_GPX_WRAPPER>` with the directory where `gpx_wrapper.ps1` is installed

4. **Configure output filename format**:
   - In the **Printer** settings, set the **Output filename format** to:
     ```
     [input_filename_base].x3g
     ```
   - This ensures the final output file has the `.x3g` extension for MakerBot compatibility

5. After slicing, the script will:
   - Inject Start G-code
   - Convert to X3G binary
   - Replace the `.gcode.pp` file with the converted binary
   - Clean up temporary files

## Script Behavior

### Input
- Accepts `.gcode.pp` files from PrusaSlicer
- Expects G-code markers: `GPX_START_MARKER` and `GPX_END_MARKER`

### Processing
1. Extracts nozzle temperature from first `M104` or `M109` command
2. Injects custom Start G-code sequence:
   - Full homing (XY to MAX, Z to MIN)
   - Origin calibration for Replicator 2
   - Nozzle heating
   - Extruder prime/purge line
3. Converts G-code to X3G format using GPX
4. Replaces input file with X3G binary

### Output
- Modified `.gcode.pp` file (binary X3G format)
- Sibling `.gcode` file automatically removed (if present)
- Exit code: `0` (success) or `1` (error)

## G-code Markers

The Start G-code block is bounded by markers:

```gcode
; --- GPX_START_MARKER ---
; (Start G-code sequence here)
; --- GPX_END_MARKER ---
```

**Important**: Your G-code must include these markers for the wrapper to inject the Start sequence.

## Start G-code Sequence

The injected Start sequence includes:

```gcode
G162 X Y F3000       ; Home XY to MAX endstops
G161 Z F1200         ; Home Z to MIN endstop
G92 X285 Y152 Z0     ; Set origin for Replicator 2
G1 Z5 F1200          ; Lift Z slightly
M104 S[temp]         ; Set nozzle temperature
M6 T0                ; Wait for nozzle temperature
G92 E0               ; Reset extruder
G1 X5 Y5 F3000       ; Move to purge start
G1 E8 F200           ; Extrude
G1 X120 F3000        ; Draw purge line
```

## Temperature Extraction

The script extracts the first nozzle temperature from:
- `M104 S<temperature>` (set nozzle temp, no wait)
- `M109 S<temperature>` (set nozzle temp, wait)

If no temperature command is found, it defaults to `200°C`.

## File Structure

```
.
├── gpx_wrapper.ps1          # Main post-processing script
├── gpx.exe                  # GPX converter binary (v2.6.8)
├── examples/                # Example G-code and configurations
│   ├── example-machine.ini
│   ├── example-pause-at-zpos.ini
│   ├── example-temperature.ini
│   ├── gpx.ini
│   └── macro-example.gcode
├── machine_inis/            # Machine-specific configurations
│   ├── r2.ini               # MakerBot Replicator 2 config
│   ├── r2h.ini              # Replicator 2 w/ Heated Build Plate
│   ├── c3.ini               # Replicator 2 Copybot 3D
│   └── (other machines)
└── scripts/                 # Utility scripts
    ├── gpx.py
    └── s3g-decompiler.py
```

## Machine Configurations

This repository includes INI files for various MakerBot printers:

These GPX configuration files are provided for reference, but the wrapper script itself currently supports only the **MakerBot Replicator 2**.

- **r2.ini** - MakerBot Replicator 2
- **r2h.ini** - Replicator 2 with Heated Build Plate
- **r2x.ini** - Replicator 2X
- **r2d.ini** - Replicator 2 Dual Extruder
- **c3.ini, c4.ini** - Replicator Copybot models
- **cp4.ini, cpp.ini** - Replicator Compact models
- **t6.ini, t7.ini** - Thingomatic models
- **z.ini** - CupCake CNC
- And more...

## Troubleshooting

### Error: "Unable to find GPX"
- Ensure `gpx.exe` is in the same directory as `gpx_wrapper.ps1`
- Check that the file name is exactly `gpx.exe`

### Error: "GPX markers not found"
- Your G-code file is likely already converted (binary X3G format)
- The script will skip injection and output will remain unchanged

### Error: "Unable to inject Start G-code"
- Verify that your G-code template includes:
  ```gcode
  ; --- GPX_START_MARKER ---
  ; --- GPX_END_MARKER ---
  ```

### Script runs but no file is created
- Check PrusaSlicer output path configuration
- Verify file permissions in the output directory
- Check PowerShell execution policy: `Get-ExecutionPolicy`

## Requirements

- **PowerShell 5.1+** (Windows)
- **GPX binary** (v2.6.8 included)
- **.NET Framework 4.5+** (for GPX)
- **PrusaSlicer 2.9.4** (tested for integration)

## Credits

This project uses the **GPX converter** originally developed by:

- **[markwal/GPX](https://github.com/markwal/GPX)** - GPX conversion library and CLI tool
  - Original GPX converter for MakerBot 3D printers
  - Supports Sailfish firmware and S3G/X3G binary formats
  - Licensed under GPLv2

Special thanks to the MakerBot community and Sailfish firmware developers for maintaining support for legacy printers.

## License

This wrapper script and configurations are provided as-is. The GPX binary is subject to its original license. See the [GPX repository](https://github.com/markwal/GPX) for licensing details.

## Support

For issues specific to:
- **GPX converter**: See [github.com/markwal/GPX](https://github.com/markwal/GPX)
- **PrusaSlicer**: See [prusa3d.com/prusaslicer](https://www.prusa3d.com/en/page/prusaslicer_en/)
- **This wrapper**: Open an issue on this repository

## Changelog

### v1.0.0 (Initial Release)
- ✅ Basic G-code injection and GPX conversion
- ✅ Temperature extraction from G-code
- ✅ PrusaSlicer post-processing integration
- ✅ Sibling `.gcode` file cleanup
- ✅ Graceful error handling
- ✅ English localization

---

**Last Updated**: April 2026
**Tested On**: MakerBot Replicator 2, Sailfish 7.7, PrusaSlicer 2.9.4
