# -*- coding: utf-8 -*-
"""
Layer type detection, URI parsing, and file discovery helpers.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from qgis.core import QgsMapLayer, QgsVectorLayer, QgsRasterLayer, QgsMeshLayer

# ---------------------------------------------------------------------------
# Provider classification
# ---------------------------------------------------------------------------

SERVICE_PROVIDERS = frozenset({
    "wms", "wfs", "wcs", "ows",
    "xyz", "tiledmesh",
    "vectortile",
    "arcgisfeatureserver", "arcgismapserver",
    "geonode",
    "esrijsonlayer",
})

DOWNLOADABLE_SERVICE_PROVIDERS = frozenset({
    "wfs",   # → GeoPackage via QgsVectorFileWriter
    "wcs",   # → GeoTIFF via QgsRasterFileWriter
})

LOCAL_FILE_PROVIDERS = frozenset({
    "ogr", "gdal", "spatialite", "mdal", "pdal",
    "delimitedtext", "gpx",
})


class LayerCategory(Enum):
    LOCAL_FILE = auto()
    MEMORY = auto()
    SERVICE_DOWNLOADABLE = auto()
    SERVICE_ONLY = auto()
    UNKNOWN = auto()


# ---------------------------------------------------------------------------
# Shapefile sidecar extensions
# ---------------------------------------------------------------------------

SHP_SIDECAR_EXTENSIONS = {
    ".dbf", ".shx", ".prj", ".cpg", ".sbn", ".sbx",
    ".fbn", ".fbx", ".ain", ".aih", ".ixs", ".mxs",
    ".atx", ".shp.xml", ".qix", ".aux.xml",
}

# Raster auxiliary files
RASTER_AUX_EXTENSIONS = {
    ".aux", ".aux.xml", ".ovr", ".rrd", ".rsc",
    ".wld", ".jgw", ".tfw", ".pgw", ".gfw",
    ".prj", ".hdr",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LayerInfo:
    """Resolved information about a single map layer."""
    layer: QgsMapLayer
    category: LayerCategory
    provider_name: str
    # For LOCAL_FILE layers:
    source_file: Optional[Path] = None      # Primary file (e.g. .shp, .gpkg, .tif)
    source_uri: str = ""                    # Full URI as-is from dataProvider
    gpkg_layer_name: Optional[str] = None  # For GPKG: |layername=...
    gpkg_layer_id: Optional[str] = None    # For GPKG: |layerid=...
    sidecar_files: list[Path] = field(default_factory=list)
    aux_files: list[Path] = field(default_factory=list)
    # Group path in layer tree (list of group names, outermost first)
    group_path: list[str] = field(default_factory=list)
    # Estimated size in bytes (source_file + sidecars)
    estimated_size: int = 0
    # Status after consolidation
    status: str = "pending"   # pending / consolidated / skipped / error / already_consolidated
    new_uri: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def layer_name(self) -> str:
        return self.layer.name() if self.layer else "?"

    @property
    def is_gpkg(self) -> bool:
        return self.source_file is not None and self.source_file.suffix.lower() == ".gpkg"

    @property
    def is_shapefile(self) -> bool:
        return self.source_file is not None and self.source_file.suffix.lower() == ".shp"

    @property
    def total_size(self) -> int:
        s = self.estimated_size
        for f in self.sidecar_files + self.aux_files:
            try:
                s += f.stat().st_size
            except OSError:
                pass
        return s


# ---------------------------------------------------------------------------
# URI parsing helpers
# ---------------------------------------------------------------------------

def parse_ogr_uri(uri: str) -> tuple[str, dict]:
    """
    Splits OGR/GDAL URI into file path and parameters.
    e.g. '/path/to/data.gpkg|layername=rivers|subset=...'
        → ('/path/to/data.gpkg', {'layername': 'rivers', 'subset': '...'})
    """
    parts = uri.split("|")
    file_path = parts[0].strip()
    params = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.strip()] = v.strip()
        else:
            params[part.strip()] = True
    return file_path, params


def reconstruct_ogr_uri(file_path: str | Path, params: dict) -> str:
    """Rebuilds OGR URI from file path and params dict."""
    base = str(file_path)
    parts = [base]
    for k, v in params.items():
        if v is True:
            parts.append(k)
        else:
            parts.append(f"{k}={v}")
    return "|".join(parts)


def parse_delimited_uri(uri: str) -> tuple[str, str]:
    """
    Delimited text URIs look like:
      file:///path/to/file.csv?delimiter=;&xField=X&yField=Y
    Returns (file_path, query_string)
    """
    if uri.startswith("file:///"):
        without_scheme = uri[7:]  # → /path/to/file.csv?...
    elif uri.startswith("file://"):
        without_scheme = uri[6:]
    else:
        without_scheme = uri

    if "?" in without_scheme:
        file_part, query = without_scheme.split("?", 1)
    else:
        file_part, query = without_scheme, ""
    return file_part, query


# ---------------------------------------------------------------------------
# Sidecar / auxiliary file discovery
# ---------------------------------------------------------------------------

def find_shapefile_sidecars(shp_path: Path) -> list[Path]:
    """Return all existing sidecar files for a .shp file."""
    stem = shp_path.stem
    parent = shp_path.parent
    found = []
    for ext in SHP_SIDECAR_EXTENSIONS:
        candidate = parent / (stem + ext)
        if candidate.exists() and candidate != shp_path:
            found.append(candidate)
    return found


def find_raster_aux_files(raster_path: Path) -> list[Path]:
    """Return all existing auxiliary files for a raster."""
    stem = raster_path.stem
    name = raster_path.name
    parent = raster_path.parent
    found = []
    for ext in RASTER_AUX_EXTENSIONS:
        for candidate in [parent / (stem + ext), parent / (name + ext)]:
            if candidate.exists() and candidate != raster_path:
                found.append(candidate)
    return found


# ---------------------------------------------------------------------------
# Main resolver function
# ---------------------------------------------------------------------------

def resolve_layer(layer: QgsMapLayer, group_path: list[str]) -> LayerInfo:
    """
    Inspect a QgsMapLayer and return a fully populated LayerInfo.
    """
    if layer is None or not layer.isValid():
        return LayerInfo(
            layer=layer,
            category=LayerCategory.UNKNOWN,
            provider_name="",
            group_path=group_path,
            status="skipped",
        )

    provider = layer.dataProvider()
    provider_name = provider.name().lower() if provider else ""
    uri = provider.dataSourceUri() if provider else ""

    # --- Memory layer ---
    if provider_name == "memory":
        return LayerInfo(
            layer=layer,
            category=LayerCategory.MEMORY,
            provider_name=provider_name,
            source_uri=uri,
            group_path=group_path,
        )

    # --- Service layer ---
    if provider_name in SERVICE_PROVIDERS:
        cat = (LayerCategory.SERVICE_DOWNLOADABLE
               if provider_name in DOWNLOADABLE_SERVICE_PROVIDERS
               else LayerCategory.SERVICE_ONLY)
        return LayerInfo(
            layer=layer,
            category=cat,
            provider_name=provider_name,
            source_uri=uri,
            group_path=group_path,
        )

    # --- Delimited text special handling ---
    if provider_name == "delimitedtext":
        file_path_str, query = parse_delimited_uri(uri)
        src = Path(file_path_str)
        if not src.is_file():
            return LayerInfo(layer=layer, category=LayerCategory.UNKNOWN,
                             provider_name=provider_name, source_uri=uri,
                             group_path=group_path)
        size = src.stat().st_size
        return LayerInfo(
            layer=layer,
            category=LayerCategory.LOCAL_FILE,
            provider_name=provider_name,
            source_file=src,
            source_uri=uri,
            group_path=group_path,
            estimated_size=size,
        )

    # --- OGR / GDAL / SpatiaLite / MDAL / PDAL ---
    if provider_name in LOCAL_FILE_PROVIDERS:
        file_path_str, params = parse_ogr_uri(uri)
        src = Path(file_path_str)
        if not src.is_file():
            # Could be a remote path or broken link
            return LayerInfo(layer=layer, category=LayerCategory.UNKNOWN,
                             provider_name=provider_name, source_uri=uri,
                             group_path=group_path)
        try:
            size = src.stat().st_size
        except OSError:
            size = 0

        info = LayerInfo(
            layer=layer,
            category=LayerCategory.LOCAL_FILE,
            provider_name=provider_name,
            source_file=src,
            source_uri=uri,
            group_path=group_path,
            estimated_size=size,
        )

        # GPKG params
        if src.suffix.lower() == ".gpkg":
            info.gpkg_layer_name = params.get("layername")
            info.gpkg_layer_id = params.get("layerid")

        # Sidecar detection
        if src.suffix.lower() == ".shp":
            info.sidecar_files = find_shapefile_sidecars(src)

        # Raster aux files
        if provider_name == "gdal":
            info.aux_files = find_raster_aux_files(src)

        return info

    # --- Fallback: try to detect by URI if it looks like a file ---
    if os.path.isfile(uri.split("|")[0].strip()):
        src = Path(uri.split("|")[0].strip())
        return LayerInfo(
            layer=layer,
            category=LayerCategory.LOCAL_FILE,
            provider_name=provider_name,
            source_file=src,
            source_uri=uri,
            group_path=group_path,
            estimated_size=src.stat().st_size if src.exists() else 0,
        )

    return LayerInfo(
        layer=layer,
        category=LayerCategory.UNKNOWN,
        provider_name=provider_name,
        source_uri=uri,
        group_path=group_path,
    )


# ---------------------------------------------------------------------------
# Layer tree traversal
# ---------------------------------------------------------------------------

def collect_layer_infos(node, group_path: list[str] = None) -> list[LayerInfo]:
    """
    Recursively walk the layer tree, resolve each layer.
    Returns list of LayerInfo objects with populated group_path.
    """
    from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer

    if group_path is None:
        group_path = []

    results = []
    for child in node.children():
        if isinstance(child, QgsLayerTreeGroup):
            results += collect_layer_infos(
                child, group_path + [child.name()]
            )
        elif isinstance(child, QgsLayerTreeLayer):
            lyr = child.layer()
            if lyr:
                results.append(resolve_layer(lyr, list(group_path)))
    return results


# ---------------------------------------------------------------------------
# Size formatting
# ---------------------------------------------------------------------------

def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"
