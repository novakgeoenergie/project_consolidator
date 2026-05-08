# Project Consolidator – QGIS Plugin

**Version:** 0.1.0 | **QGIS:** ≥ 3.34 (tested on 3.40 LTR)  
**Author:** Petr Novak  
**Languages:** English · Deutsch · Čeština

---

## What it does

Creates a self-contained, portable copy of your QGIS project:

```
MyProject_consolidated_20260401/
├── MyProject.qgs          ← copy with updated layer paths
└── Layers/
    ├── GroupA/            ← mirrors layer group structure
    │   └── data.gpkg
    ├── roads.gpkg
    └── dem.tif
```

- **Original project is never modified.**
- All local file layers are copied into `Layers/` (or group subdirectories).
- Layer styling, rendering order, and project settings are fully preserved.
- GeoPackages containing multiple layers are copied once (not per-layer).
- Optional: convert Shapefiles to GeoPackage, save memory layers, download WFS/WCS.

---

## Installation

1. Download / clone this repository.
2. Copy the `project_consolidator/` folder to your QGIS plugins directory:
   - **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS and enable the plugin via **Plugins → Manage and Install Plugins**.

---

## Usage

1. Open (and save) your QGIS project.
2. Click the **Project Consolidator** toolbar button or go to **Plugins → Project Consolidator**.
3. The dialog opens and **automatically analyses** the project.
4. Configure options:
   - **Output directory** (default: `<ProjectFolder>/<ProjectName>_consolidated_YYYYMMDD/`)
   - **Preserve group folder structure** – mirrors layer tree groups as subdirectories
   - **Convert Shapefiles to GeoPackage** – opt-in, creates per-layer `.gpkg` files
   - **Filename collision strategy** – Subdirectory (default) / Numeric suffix / Ask
   - **Memory layers** – check which in-memory layers to save as GeoPackage
   - **Service layers** – optionally download WFS/WCS layers as local files
   - **Language** – EN / DE / CS, persisted in QGIS settings
5. Click **Consolidate**. Progress is shown inline.
6. On completion, click **Open consolidated project** to switch to it.

---

## Supported layer types

| Type | Provider | Action |
|---|---|---|
| GeoPackage | ogr | Copy whole file once |
| Shapefile | ogr | Copy + all sidecar files (.dbf, .shx, .prj, …) |
| GeoTIFF / raster | gdal | Copy + auxiliary files (.aux.xml, world files) |
| GeoJSON, CSV, DXF | ogr | Copy |
| Delimited text | delimitedtext | Copy file, rebuild URI |
| Mesh (.nc, .2dm) | mdal | Copy |
| Point cloud (.las/.laz) | pdal | Copy |
| Memory layer | memory | Save to GeoPackage (opt-in per layer) |
| WFS | wfs | Download as GeoPackage (optional) |
| WCS | wcs | Download as GeoTIFF (optional) |
| WMS / XYZ / Vector tiles | — | Skipped (service, no local file) |

---

## Known limitations / TODO

- [ ] WMS/WMTS export as raster (gdal_translate integration)
- [ ] Progress running in QThread – UI may briefly freeze on very large files (copy is blocking)
- [ ] No support for PostgreSQL/PostGIS layers (intentional – these are not "local file" layers)
- [ ] Compressed project files (`.qgz`) not yet tested
- [ ] Unit tests

---

## File structure

```
project_consolidator/
├── __init__.py              QGIS classFactory entry
├── metadata.txt             Plugin metadata
├── project_consolidator.py  Plugin class (menu / toolbar)
├── consolidator.py          Core consolidation engine
├── layer_resolver.py        Layer type detection & URI parsing
├── i18n.py                  Translations (EN/DE/CS)
├── dialogs/
│   ├── __init__.py
│   └── analysis_dialog.py  Main dialog (analysis + options + progress)
└── resources/
    └── icon.svg
```

---

## License

GNU GENERAL PUBLIC LICENSE – see LICENSE file.
