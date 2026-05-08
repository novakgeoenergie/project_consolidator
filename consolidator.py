# -*- coding: utf-8 -*-
"""
Core consolidation engine.
Creates a consolidated copy of the QGIS project with all local layers
relocated to a Layers/ subdirectory.
"""

from __future__ import annotations

import shutil
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from qgis.core import (
    QgsProject, QgsMapLayer, QgsVectorLayer, QgsRasterLayer,
    QgsDataProvider, QgsVectorFileWriter, QgsRasterFileWriter,
    QgsRasterPipe, QgsRasterProjector, Qgis,
)
from qgis.PyQt.QtCore import QObject, pyqtSignal

from .layer_resolver import (
    LayerInfo, LayerCategory,
    reconstruct_ogr_uri, parse_ogr_uri, parse_delimited_uri,
    format_size,
)
from .i18n import t

log = logging.getLogger("project_consolidator")


# ---------------------------------------------------------------------------
# Options dataclass
# ---------------------------------------------------------------------------

@dataclass
class ConsolidationOptions:
    output_dir: Path                         # Root of consolidated project
    preserve_group_subdirs: bool = True      # Mirror group structure in Layers/
    collision_strategy: str = "subdir"       # 'subdir' | 'suffix' | 'ask'
    convert_shp_to_gpkg: bool = False        # opt-in
    memory_layers_to_save: list[str] = field(default_factory=list)   # layer IDs
    download_wfs: bool = False
    download_wcs: bool = False
    language: str = "en"


@dataclass
class ConsolidationResult:
    consolidated: list[LayerInfo] = field(default_factory=list)
    skipped: list[LayerInfo] = field(default_factory=list)
    errors: list[LayerInfo] = field(default_factory=list)
    already_done: list[LayerInfo] = field(default_factory=list)
    output_project_path: Optional[Path] = None

    @property
    def total(self):
        return len(self.consolidated) + len(self.skipped) + len(self.errors) + len(self.already_done)


# ---------------------------------------------------------------------------
# Collision resolution
# ---------------------------------------------------------------------------

def resolve_collision_subdir(dest_dir: Path, src_file: Path) -> Path:
    """Create a subdirectory named after original parent folder."""
    sub = dest_dir / src_file.parent.name
    sub.mkdir(parents=True, exist_ok=True)
    return sub / src_file.name


def resolve_collision_suffix(dest_dir: Path, src_file: Path) -> Path:
    """Append _2, _3, … until name is unique."""
    candidate = dest_dir / src_file.name
    counter = 2
    while candidate.exists():
        candidate = dest_dir / f"{src_file.stem}_{counter}{src_file.suffix}"
        counter += 1
    return candidate


# ---------------------------------------------------------------------------
# Main consolidator class
# ---------------------------------------------------------------------------

class ProjectConsolidator(QObject):
    """
    Signals:
        progress(current: int, total: int, message: str)
        finished(result: ConsolidationResult)
        error(message: str)
    """

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        layer_infos: list[LayerInfo],
        options: ConsolidationOptions,
        collision_callback: Optional[Callable] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.layer_infos = layer_infos
        self.options = options
        self.collision_callback = collision_callback   # fn(src_path, dest_dir) → Path or None (skip)
        self._cancelled = False

        # Cache: source GPKG path → destination GPKG path (copy only once)
        self._gpkg_copy_cache: dict[Path, Path] = {}
        # Cache: any other local file → destination path (copy only once)
        # Shared files (used by multiple layers) land in Layers/ root, not in a group subdir,
        # so all layers referencing them get a consistent URI.
        self._file_copy_cache: dict[Path, Path] = {}
        # Cache: collision resolution preference if user chose "apply to all"
        self._collision_global: Optional[str] = None
        # Pre-compute which source files appear more than once across all layer infos
        from collections import Counter
        src_counts = Counter(
            li.source_file for li in layer_infos
            if li.category == LayerCategory.LOCAL_FILE and li.source_file
        )
        self._shared_sources: frozenset[Path] = frozenset(
            src for src, count in src_counts.items() if count > 1
        )

    def cancel(self):
        self._cancelled = True

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def run(self) -> ConsolidationResult:
        opts = self.options
        result = ConsolidationResult()

        # 1. Validate and prepare output directory
        project = QgsProject.instance()
        src_project_path = Path(project.fileName())
        if not src_project_path.exists():
            self.error.emit(t("err_unsaved_project"))
            return result

        out_dir = opts.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        layers_root = out_dir / "Layers"
        layers_root.mkdir(exist_ok=True)
        self._layers_root = layers_root  # accessible by all _copy_* helpers

        # 2. Copy project file to output dir (we'll modify the copy later)
        out_project_path = out_dir / src_project_path.name
        shutil.copy2(src_project_path, out_project_path)

        # 3. Load the project copy into a *separate* QgsProject instance
        # so we don't disturb the currently open project in QGIS
        shadow = QgsProject()
        if not shadow.read(str(out_project_path)):
            self.error.emit(f"Could not read project copy at {out_project_path}")
            return result

        shadow.setFilePathStorage(Qgis.FilePathType.Relative)

        # Build lookup: layer ID → LayerInfo
        info_by_id = {li.layer.id(): li for li in self.layer_infos}

        total = len(self.layer_infos)

        for idx, info in enumerate(self.layer_infos):
            if self._cancelled:
                break

            shadow_layer = shadow.mapLayer(info.layer.id())

            # ----------------------------------------------------------------
            # MEMORY layers
            # ----------------------------------------------------------------
            if info.category == LayerCategory.MEMORY:
                if info.layer.id() in opts.memory_layers_to_save:
                    msg = t("progress_saving_memory", info.layer_name)
                    self.progress.emit(idx + 1, total, msg)
                    dest_dir = self._get_dest_dir(layers_root, info)
                    new_path = dest_dir / f"{self._safe_name(info.layer_name)}.gpkg"
                    ok = self._save_memory_layer(info.layer, new_path)
                    if ok and shadow_layer:
                        new_uri = f"{new_path}|layername={self._safe_name(info.layer_name)}"
                        self._update_shadow_source(shadow_layer, new_uri, "ogr")
                        info.status = "consolidated"
                        info.new_uri = new_uri
                        result.consolidated.append(info)
                    else:
                        info.status = "error"
                        result.errors.append(info)
                else:
                    info.status = "skipped"
                    result.skipped.append(info)
                continue

            # ----------------------------------------------------------------
            # SERVICE layers
            # ----------------------------------------------------------------
            if info.category == LayerCategory.SERVICE_DOWNLOADABLE:
                should_download = (
                    (info.provider_name == "wfs" and opts.download_wfs) or
                    (info.provider_name == "wcs" and opts.download_wcs)
                )
                if should_download:
                    msg = t("progress_copying", info.layer_name)
                    self.progress.emit(idx + 1, total, msg)
                    dest_dir = self._get_dest_dir(layers_root, info)
                    self._download_service_layer(info, dest_dir, shadow_layer, result)
                else:
                    info.status = "skipped"
                    result.skipped.append(info)
                continue

            if info.category == LayerCategory.SERVICE_ONLY:
                info.status = "skipped"
                result.skipped.append(info)
                continue

            if info.category == LayerCategory.UNKNOWN:
                info.status = "skipped"
                result.skipped.append(info)
                continue

            # ----------------------------------------------------------------
            # LOCAL FILE layers
            # ----------------------------------------------------------------
            msg = t("progress_copying", info.source_file.name if info.source_file else "?")
            self.progress.emit(idx + 1, total, msg)

            dest_dir = self._get_dest_dir(layers_root, info)
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Already inside the output Layers/ directory? Skip.
            try:
                info.source_file.relative_to(layers_root)
                info.status = "already_consolidated"
                result.already_done.append(info)
                continue
            except ValueError:
                pass

            if info.is_gpkg:
                self._handle_gpkg(info, dest_dir, shadow_layer, result)
            elif info.is_shapefile and opts.convert_shp_to_gpkg:
                self._convert_shp_to_gpkg(info, dest_dir, shadow_layer, result)
            elif info.is_shapefile:
                self._copy_shapefile(info, dest_dir, shadow_layer, result)
            elif info.provider_name == "delimitedtext":
                self._copy_delimited(info, dest_dir, shadow_layer, result)
            else:
                self._copy_generic(info, dest_dir, shadow_layer, result)

        # 4. Save the shadow project (QGIS recalculates relative paths)
        self.progress.emit(total, total, t("progress_saving_project"))
        shadow.write(str(out_project_path))

        result.output_project_path = out_project_path
        self.finished.emit(result)
        return result

    # -----------------------------------------------------------------------
    # Destination directory helper
    # -----------------------------------------------------------------------

    def _get_dest_dir(self, layers_root: Path, info: LayerInfo) -> Path:
        if self.options.preserve_group_subdirs and info.group_path:
            # Sanitize group names for filesystem use
            safe_parts = [self._safe_name(g) for g in info.group_path]
            return layers_root / Path(*safe_parts)
        return layers_root

    def _get_effective_dest_dir(self, layers_root: Path, info: LayerInfo) -> Path:
        """
        For files shared by multiple layers: always use Layers/ root
        so every referencing layer gets the same URI.
        For unique files: use the group-aware subdirectory.
        """
        if info.source_file and info.source_file in self._shared_sources:
            return layers_root   # ← shared → root, no group subdir
        return self._get_dest_dir(layers_root, info)

    # -----------------------------------------------------------------------
    # Collision resolution
    # -----------------------------------------------------------------------

    def _resolve_dest_path(self, dest_dir: Path, src_file: Path) -> Optional[Path]:
        """
        Returns destination path, handling collisions per strategy.
        Returns None if user chose 'skip'.
        """
        candidate = dest_dir / src_file.name
        if not candidate.exists():
            return candidate

        strategy = self._collision_global or self.options.collision_strategy

        if strategy == "subdir":
            return resolve_collision_subdir(dest_dir, src_file)
        elif strategy == "suffix":
            return resolve_collision_suffix(dest_dir, src_file)
        elif strategy == "ask" and self.collision_callback:
            choice, apply_all = self.collision_callback(src_file, dest_dir)
            if apply_all and choice:
                self._collision_global = choice
            if choice == "subdir":
                return resolve_collision_subdir(dest_dir, src_file)
            elif choice == "suffix":
                return resolve_collision_suffix(dest_dir, src_file)
            else:
                return None   # skip
        else:
            # Fallback to subdir
            return resolve_collision_subdir(dest_dir, src_file)

    # -----------------------------------------------------------------------
    # GeoPackage handler
    # -----------------------------------------------------------------------

    def _handle_gpkg(self, info: LayerInfo, dest_dir: Path,
                     shadow_layer, result: ConsolidationResult):
        src = info.source_file

        if src not in self._gpkg_copy_cache:
            dst = self._resolve_dest_path(dest_dir, src)
            if dst is None:
                info.status = "skipped"
                result.skipped.append(info)
                return
            try:
                shutil.copy2(src, dst)
                self._gpkg_copy_cache[src] = dst
            except OSError as e:
                info.status = "error"
                info.error_message = str(e)
                log.error(t("err_copy_failed", src, e))
                result.errors.append(info)
                return
        else:
            dst = self._gpkg_copy_cache[src]

        # Rebuild URI preserving layername/layerid/subset
        _, params = parse_ogr_uri(info.source_uri)
        new_uri = reconstruct_ogr_uri(dst, params)

        if shadow_layer and self._update_shadow_source(shadow_layer, new_uri, info.provider_name):
            info.status = "consolidated"
            info.new_uri = new_uri
            result.consolidated.append(info)
        else:
            info.status = "error"
            info.error_message = t("err_layer_invalid_after", info.layer_name)
            result.errors.append(info)

    # -----------------------------------------------------------------------
    # Shapefile handlers
    # -----------------------------------------------------------------------

    def _copy_shapefile(self, info: LayerInfo, dest_dir: Path,
                        shadow_layer, result: ConsolidationResult):
        src = info.source_file

        # --- shared source: reuse already-copied path ---
        if src in self._file_copy_cache:
            dst = self._file_copy_cache[src]
        else:
            effective_dir = self._get_effective_dest_dir(
                dest_dir.parent if dest_dir != dest_dir.parent else dest_dir,
                info
            ) if False else dest_dir  # dest_dir already computed by caller; recalc below
            # Recalculate with shared-source awareness (caller passed group dir)
            # We need layers_root — store it as instance var set in run()
            effective_dir = self._get_effective_dest_dir(self._layers_root, info)
            effective_dir.mkdir(parents=True, exist_ok=True)

            dst = self._resolve_dest_path(effective_dir, src)
            if dst is None:
                info.status = "skipped"
                result.skipped.append(info)
                return

            actual_dest_dir = dst.parent
            actual_dest_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                for sidecar in info.sidecar_files:
                    shutil.copy2(sidecar, actual_dest_dir / sidecar.name)
            except OSError as e:
                info.status = "error"
                info.error_message = str(e)
                result.errors.append(info)
                return
            self._file_copy_cache[src] = dst

        _, params = parse_ogr_uri(info.source_uri)
        new_uri = reconstruct_ogr_uri(dst, params)

        if shadow_layer and self._update_shadow_source(shadow_layer, new_uri, info.provider_name):
            info.status = "consolidated"
            info.new_uri = new_uri
            result.consolidated.append(info)
        else:
            info.status = "error"
            info.error_message = t("err_layer_invalid_after", info.layer_name)
            result.errors.append(info)

    def _convert_shp_to_gpkg(self, info: LayerInfo, dest_dir: Path,
                              shadow_layer, result: ConsolidationResult):
        gpkg_name = f"{info.source_file.stem}.gpkg"
        dst = dest_dir / gpkg_name
        if dst.exists():
            dst = resolve_collision_suffix(dest_dir, dst)

        save_opts = QgsVectorFileWriter.SaveVectorOptions()
        save_opts.driverName = "GPKG"
        save_opts.layerName = info.source_file.stem
        save_opts.fileEncoding = "UTF-8"

        err = QgsVectorFileWriter.writeAsVectorFormatV3(
            info.layer,
            str(dst),
            QgsProject.instance().transformContext(),
            save_opts,
        )
        if err[0] != QgsVectorFileWriter.WriterError.NoError:
            info.status = "error"
            info.error_message = f"SHP→GPKG conversion failed: {err[1]}"
            result.errors.append(info)
            return

        new_uri = f"{dst}|layername={info.source_file.stem}"
        if shadow_layer and self._update_shadow_source(shadow_layer, new_uri, "ogr"):
            info.status = "consolidated"
            info.new_uri = new_uri
            result.consolidated.append(info)
        else:
            info.status = "error"
            info.error_message = t("err_layer_invalid_after", info.layer_name)
            result.errors.append(info)

    # -----------------------------------------------------------------------
    # Generic file copy (GeoTIFF, GeoJSON, CSV, mesh, point cloud…)
    # -----------------------------------------------------------------------

    def _copy_generic(self, info: LayerInfo, dest_dir: Path,
                      shadow_layer, result: ConsolidationResult):
        src = info.source_file

        # --- shared source: reuse already-copied path ---
        if src in self._file_copy_cache:
            dst = self._file_copy_cache[src]
        else:
            effective_dir = self._get_effective_dest_dir(self._layers_root, info)
            effective_dir.mkdir(parents=True, exist_ok=True)

            dst = self._resolve_dest_path(effective_dir, src)
            if dst is None:
                info.status = "skipped"
                result.skipped.append(info)
                return

            actual_dest_dir = dst.parent
            actual_dest_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                for aux in info.aux_files:
                    shutil.copy2(aux, actual_dest_dir / aux.name)
            except OSError as e:
                info.status = "error"
                info.error_message = str(e)
                result.errors.append(info)
                return
            self._file_copy_cache[src] = dst

        _, params = parse_ogr_uri(info.source_uri)
        new_uri = reconstruct_ogr_uri(dst, params)

        if shadow_layer and self._update_shadow_source(shadow_layer, new_uri, info.provider_name):
            info.status = "consolidated"
            info.new_uri = new_uri
            result.consolidated.append(info)
        else:
            info.status = "error"
            info.error_message = t("err_layer_invalid_after", info.layer_name)
            result.errors.append(info)

    def _copy_delimited(self, info: LayerInfo, dest_dir: Path,
                        shadow_layer, result: ConsolidationResult):
        src = info.source_file

        if src in self._file_copy_cache:
            dst = self._file_copy_cache[src]
        else:
            effective_dir = self._get_effective_dest_dir(self._layers_root, info)
            effective_dir.mkdir(parents=True, exist_ok=True)
            dst = self._resolve_dest_path(effective_dir, src)
            if dst is None:
                info.status = "skipped"
                result.skipped.append(info)
                return
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                info.status = "error"
                info.error_message = str(e)
                result.errors.append(info)
                return
            self._file_copy_cache[src] = dst

        file_str, query = parse_delimited_uri(info.source_uri)
        new_uri = f"file:///{dst}" + (f"?{query}" if query else "")

        if shadow_layer and self._update_shadow_source(shadow_layer, new_uri, "delimitedtext"):
            info.status = "consolidated"
            info.new_uri = new_uri
            result.consolidated.append(info)
        else:
            info.status = "error"
            info.error_message = t("err_layer_invalid_after", info.layer_name)
            result.errors.append(info)

    # -----------------------------------------------------------------------
    # Memory layer: save to GPKG
    # -----------------------------------------------------------------------

    def _save_memory_layer(self, layer: QgsMapLayer, dest_path: Path) -> bool:
        if not isinstance(layer, QgsVectorLayer):
            return False
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        save_opts = QgsVectorFileWriter.SaveVectorOptions()
        save_opts.driverName = "GPKG"
        save_opts.layerName = self._safe_name(layer.name())
        save_opts.fileEncoding = "UTF-8"
        err = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            str(dest_path),
            QgsProject.instance().transformContext(),
            save_opts,
        )
        return err[0] == QgsVectorFileWriter.WriterError.NoError

    # -----------------------------------------------------------------------
    # Service layer download
    # -----------------------------------------------------------------------

    def _download_service_layer(self, info: LayerInfo, dest_dir: Path,
                                 shadow_layer, result: ConsolidationResult):
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe = self._safe_name(info.layer_name)

        if info.provider_name == "wfs" and isinstance(info.layer, QgsVectorLayer):
            dst = dest_dir / f"{safe}.gpkg"
            save_opts = QgsVectorFileWriter.SaveVectorOptions()
            save_opts.driverName = "GPKG"
            save_opts.layerName = safe
            save_opts.fileEncoding = "UTF-8"
            err = QgsVectorFileWriter.writeAsVectorFormatV3(
                info.layer,
                str(dst),
                QgsProject.instance().transformContext(),
                save_opts,
            )
            if err[0] == QgsVectorFileWriter.WriterError.NoError:
                new_uri = f"{dst}|layername={safe}"
                if shadow_layer and self._update_shadow_source(shadow_layer, new_uri, "ogr"):
                    info.status = "consolidated"
                    info.new_uri = new_uri
                    result.consolidated.append(info)
                    return
            info.status = "error"
            info.error_message = f"WFS download failed: {err[1] if err else 'unknown'}"
            result.errors.append(info)

        elif info.provider_name == "wcs" and isinstance(info.layer, QgsRasterLayer):
            dst = dest_dir / f"{safe}.tif"
            pipe = QgsRasterPipe()
            pipe.set(info.layer.dataProvider().clone())
            writer = QgsRasterFileWriter(str(dst))
            err = writer.writeRaster(
                pipe,
                info.layer.width(),
                info.layer.height(),
                info.layer.extent(),
                info.layer.crs(),
            )
            if err == QgsRasterFileWriter.WriterError.NoError:
                if shadow_layer and self._update_shadow_source(shadow_layer, str(dst), "gdal"):
                    info.status = "consolidated"
                    info.new_uri = str(dst)
                    result.consolidated.append(info)
                    return
            info.status = "error"
            info.error_message = "WCS download failed"
            result.errors.append(info)
        else:
            info.status = "skipped"
            result.skipped.append(info)

    # -----------------------------------------------------------------------
    # Source update on shadow project layer
    # -----------------------------------------------------------------------

    def _update_shadow_source(self, shadow_layer: QgsMapLayer,
                               new_uri: str, provider: str) -> bool:
        """Update data source on the shadow project copy. Returns True if valid."""
        opts = QgsDataProvider.ProviderOptions()
        shadow_layer.setDataSource(new_uri, shadow_layer.name(), provider, opts)
        valid = shadow_layer.isValid()
        if not valid:
            log.warning(t("err_layer_invalid_after", shadow_layer.name()))
        return valid

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    @staticmethod
    def _safe_name(name: str) -> str:
        """Remove characters unsafe for filenames."""
        import re
        return re.sub(r'[\\/:*?"<>|]', "_", name).strip()
