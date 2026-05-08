# -*- coding: utf-8 -*-
"""
Main dialog: shows analysis results and lets user configure all options
before consolidation starts. All decisions are made here — nothing runs
until the user clicks "Consolidate".
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QCheckBox, QComboBox, QGroupBox,
    QFileDialog, QLineEdit, QScrollArea, QWidget,
    QProgressBar, QTextEdit, QSizePolicy, QSpacerItem,
    QButtonGroup, QRadioButton, QFrame, QListWidget,
    QListWidgetItem, QMessageBox,
)
from qgis.PyQt.QtGui import QFont, QColor, QIcon

from ..i18n import I18n, t
from ..layer_resolver import (
    LayerInfo, LayerCategory, collect_layer_infos, format_size
)
from ..consolidator import (
    ConsolidationOptions, ConsolidationResult, ProjectConsolidator
)

LANG_DISPLAY = {"en": "English", "de": "Deutsch", "cs": "Čeština"}
LANG_CODES = list(LANG_DISPLAY.keys())


class AnalysisDialog(QDialog):
    """
    Multi-section dialog:
      1) Language selector (top, instant retranslation)
      2) Analysis summary
      3) Output directory selector
      4) Options (collision, groups, shp→gpkg)
      5) Memory layer checklist (if any)
      6) Service download toggles (if applicable)
      7) Progress bar (hidden until consolidation starts)
      [Analyze] → [Consolidate] / [Cancel]
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("analysis_title"))
        self.setMinimumWidth(640)
        self.setMinimumHeight(520)

        self._layer_infos: list[LayerInfo] = []
        self._worker: Optional[ProjectConsolidator] = None
        self._worker_thread: Optional[QThread] = None
        self._result: Optional[ConsolidationResult] = None

        self._build_ui()
        self._connect_signals()
        self._auto_analyze()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Language bar ────────────────────────────────────────────────────
        lang_bar = QHBoxLayout()
        self._lang_label = QLabel(t("language_label") + ":")
        self._lang_combo = QComboBox()
        for code, display in LANG_DISPLAY.items():
            self._lang_combo.addItem(display, code)
        self._lang_combo.setCurrentIndex(LANG_CODES.index(I18n.get_language()))
        self._lang_combo.setMaximumWidth(140)
        lang_bar.addWidget(self._lang_label)
        lang_bar.addWidget(self._lang_combo)
        lang_bar.addStretch()
        root.addLayout(lang_bar)

        # Separator
        root.addWidget(self._separator())

        # ── Analysis summary ────────────────────────────────────────────────
        self._grp_analysis = QGroupBox(t("section_analysis"))
        self._analysis_grid = QGridLayout(self._grp_analysis)
        self._analysis_grid.setColumnStretch(1, 1)
        self._summary_labels: dict[str, QLabel] = {}
        for row, key in enumerate([
            "summary_project",
            "summary_local_layers",
            "summary_gpkg_files",
            "summary_shp_files",
            "summary_memory_layers",
            "summary_service_layers",
            "summary_already_consolidated",
            "summary_estimated_size",
        ]):
            lbl_key = QLabel(t(key) + ":")
            lbl_val = QLabel("—")
            lbl_val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._analysis_grid.addWidget(lbl_key, row, 0)
            self._analysis_grid.addWidget(lbl_val, row, 1)
            self._summary_labels[key] = lbl_val
        root.addWidget(self._grp_analysis)

        # ── Output ──────────────────────────────────────────────────────────
        self._grp_output = QGroupBox(t("section_output"))
        out_layout = QVBoxLayout(self._grp_output)
        dir_row = QHBoxLayout()
        self._out_dir_label = QLabel(t("output_dir_label"))
        self._out_dir_edit = QLineEdit()
        self._out_dir_edit.setReadOnly(True)
        self._out_dir_btn = QPushButton(t("output_dir_browse"))
        dir_row.addWidget(self._out_dir_label)
        dir_row.addWidget(self._out_dir_edit, 1)
        dir_row.addWidget(self._out_dir_btn)
        out_layout.addLayout(dir_row)
        root.addWidget(self._grp_output)

        # ── Options ─────────────────────────────────────────────────────────
        self._grp_options = QGroupBox(t("section_options"))
        opt_layout = QVBoxLayout(self._grp_options)

        self._chk_groups = QCheckBox(t("opt_group_subdirs"))
        self._chk_groups.setChecked(True)
        self._chk_shp2gpkg = QCheckBox(t("opt_shp_to_gpkg"))
        self._chk_shp2gpkg.setChecked(False)

        # Collision strategy
        coll_row = QHBoxLayout()
        self._coll_label = QLabel(t("opt_collision_label"))
        self._coll_combo = QComboBox()
        self._coll_combo.addItem(t("collision_subdir"), "subdir")
        self._coll_combo.addItem(t("collision_suffix"), "suffix")
        self._coll_combo.addItem(t("collision_ask"), "ask")
        coll_row.addWidget(self._coll_label)
        coll_row.addWidget(self._coll_combo, 1)

        opt_layout.addWidget(self._chk_groups)
        opt_layout.addWidget(self._chk_shp2gpkg)
        opt_layout.addLayout(coll_row)
        root.addWidget(self._grp_options)

        # ── Memory layers ────────────────────────────────────────────────────
        self._grp_memory = QGroupBox(t("section_memory"))
        mem_layout = QVBoxLayout(self._grp_memory)
        self._mem_list = QListWidget()
        self._mem_list.setSelectionMode(QListWidget.NoSelection)
        self._mem_empty_label = QLabel(t("no_memory_layers"))
        self._mem_empty_label.setAlignment(Qt.AlignCenter)
        mem_layout.addWidget(self._mem_list)
        mem_layout.addWidget(self._mem_empty_label)
        self._grp_memory.setVisible(False)
        root.addWidget(self._grp_memory)

        # ── Service layers ───────────────────────────────────────────────────
        self._grp_services = QGroupBox(t("section_services"))
        svc_layout = QVBoxLayout(self._grp_services)
        self._chk_dl_wfs = QCheckBox(t("opt_download_wfs"))
        self._chk_dl_wcs = QCheckBox(t("opt_download_wcs"))
        self._svc_empty_label = QLabel(t("no_service_layers"))
        self._svc_empty_label.setAlignment(Qt.AlignCenter)
        svc_layout.addWidget(self._chk_dl_wfs)
        svc_layout.addWidget(self._chk_dl_wcs)
        svc_layout.addWidget(self._svc_empty_label)
        self._grp_services.setVisible(False)
        root.addWidget(self._grp_services)

        # ── Progress bar ─────────────────────────────────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_label = QLabel("")
        self._progress_label.setVisible(False)
        root.addWidget(self._progress_bar)
        root.addWidget(self._progress_label)

        # ── Log / result ─────────────────────────────────────────────────────
        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setMaximumHeight(100)
        self._log_box.setVisible(False)
        root.addWidget(self._log_box)

        # ── Buttons ──────────────────────────────────────────────────────────
        root.addWidget(self._separator())
        btn_row = QHBoxLayout()
        self._btn_consolidate = QPushButton(t("btn_consolidate"))
        self._btn_consolidate.setEnabled(False)
        self._btn_open = QPushButton(t("btn_open_project"))
        self._btn_open.setVisible(False)
        self._btn_cancel = QPushButton(t("btn_cancel"))

        btn_row.addWidget(self._btn_consolidate)
        btn_row.addWidget(self._btn_open)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_cancel)
        root.addLayout(btn_row)

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    # -----------------------------------------------------------------------
    # Signal wiring
    # -----------------------------------------------------------------------

    def _connect_signals(self):
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self._out_dir_btn.clicked.connect(self._browse_output)
        self._btn_consolidate.clicked.connect(self._start_consolidation)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_open.clicked.connect(self._open_result_project)

    # -----------------------------------------------------------------------
    # Language
    # -----------------------------------------------------------------------

    def _on_language_changed(self, idx: int):
        lang = self._lang_combo.itemData(idx)
        I18n.set_language(lang)
        self._retranslate()

    def _retranslate(self):
        """Retranslate all labels without rebuilding the UI."""
        self.setWindowTitle(t("analysis_title"))
        self._lang_label.setText(t("language_label") + ":")
        self._grp_analysis.setTitle(t("section_analysis"))
        self._grp_output.setTitle(t("section_output"))
        self._grp_options.setTitle(t("section_options"))
        self._grp_memory.setTitle(t("section_memory"))
        self._grp_services.setTitle(t("section_services"))
        self._out_dir_label.setText(t("output_dir_label"))
        self._out_dir_btn.setText(t("output_dir_browse"))
        self._chk_groups.setText(t("opt_group_subdirs"))
        self._chk_shp2gpkg.setText(t("opt_shp_to_gpkg"))
        self._coll_label.setText(t("opt_collision_label"))
        self._coll_combo.setItemText(0, t("collision_subdir"))
        self._coll_combo.setItemText(1, t("collision_suffix"))
        self._coll_combo.setItemText(2, t("collision_ask"))
        self._chk_dl_wfs.setText(t("opt_download_wfs"))
        self._chk_dl_wcs.setText(t("opt_download_wcs"))
        self._mem_empty_label.setText(t("no_memory_layers"))
        self._svc_empty_label.setText(t("no_service_layers"))
        self._btn_consolidate.setText(t("btn_consolidate"))
        self._btn_open.setText(t("btn_open_project"))
        self._btn_cancel.setText(t("btn_cancel"))
        for key, lbl in self._summary_labels.items():
            row = list(self._summary_labels.keys()).index(key)
            item = self._analysis_grid.itemAtPosition(row, 0)
            if item:
                item.widget().setText(t(key) + ":")

    # -----------------------------------------------------------------------
    # Analysis
    # -----------------------------------------------------------------------

    def _auto_analyze(self):
        project = QgsProject.instance()
        if not project.fileName():
            for lbl in self._summary_labels.values():
                lbl.setText("—")
            return

        root = project.layerTreeRoot()
        self._layer_infos = collect_layer_infos(root)

        local = [li for li in self._layer_infos if li.category == LayerCategory.LOCAL_FILE]
        memory = [li for li in self._layer_infos if li.category == LayerCategory.MEMORY]
        svc_dl = [li for li in self._layer_infos if li.category == LayerCategory.SERVICE_DOWNLOADABLE]
        svc_only = [li for li in self._layer_infos if li.category == LayerCategory.SERVICE_ONLY]

        gpkg_files = set(li.source_file for li in local if li.is_gpkg)
        shp_files = set(li.source_file for li in local if li.is_shapefile)

        proj_path = Path(project.fileName())
        layers_root = proj_path.parent / "Layers"
        already = [li for li in local
                   if li.source_file and layers_root in li.source_file.parents]

        total_size = sum(li.total_size for li in local if li not in already)

        # Summary labels
        self._summary_labels["summary_project"].setText(proj_path.name)
        self._summary_labels["summary_local_layers"].setText(str(len(local)))
        self._summary_labels["summary_gpkg_files"].setText(str(len(gpkg_files)))
        self._summary_labels["summary_shp_files"].setText(str(len(shp_files)))
        self._summary_labels["summary_memory_layers"].setText(str(len(memory)))
        svc_count = len(svc_dl) + len(svc_only)
        self._summary_labels["summary_service_layers"].setText(str(svc_count))
        self._summary_labels["summary_already_consolidated"].setText(str(len(already)))
        self._summary_labels["summary_estimated_size"].setText(format_size(total_size))

        # Suggest output directory
        ts = datetime.datetime.now().strftime("%Y%m%d")
        suggested = proj_path.parent / f"{proj_path.stem}_consolidated_{ts}"
        self._out_dir_edit.setText(str(suggested))

        # Memory layers list
        if memory:
            self._mem_list.clear()
            for li in memory:
                item = QListWidgetItem(li.layer_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setData(Qt.UserRole, li.layer.id())
                self._mem_list.addItem(item)
            self._mem_empty_label.setVisible(False)
            self._mem_list.setVisible(True)
            self._grp_memory.setVisible(True)
        else:
            self._grp_memory.setVisible(False)

        # Service layers
        has_downloadable = bool(svc_dl)
        self._chk_dl_wfs.setVisible(any(li.provider_name == "wfs" for li in svc_dl))
        self._chk_dl_wcs.setVisible(any(li.provider_name == "wcs" for li in svc_dl))
        self._svc_empty_label.setVisible(not has_downloadable)
        self._grp_services.setVisible(svc_count > 0)

        self._btn_consolidate.setEnabled(True)

    # -----------------------------------------------------------------------
    # Output directory
    # -----------------------------------------------------------------------

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(
            self, t("output_dir_label"),
            self._out_dir_edit.text() or str(Path.home()),
        )
        if path:
            self._out_dir_edit.setText(path)

    # -----------------------------------------------------------------------
    # Consolidation
    # -----------------------------------------------------------------------

    def _build_options(self) -> ConsolidationOptions:
        # Memory layers to save
        memory_ids = []
        for i in range(self._mem_list.count()):
            item = self._mem_list.item(i)
            if item.checkState() == Qt.Checked:
                memory_ids.append(item.data(Qt.UserRole))

        return ConsolidationOptions(
            output_dir=Path(self._out_dir_edit.text()),
            preserve_group_subdirs=self._chk_groups.isChecked(),
            collision_strategy=self._coll_combo.currentData(),
            convert_shp_to_gpkg=self._chk_shp2gpkg.isChecked(),
            memory_layers_to_save=memory_ids,
            download_wfs=self._chk_dl_wfs.isChecked(),
            download_wcs=self._chk_dl_wcs.isChecked(),
            language=I18n.get_language(),
        )

    def _start_consolidation(self):
        if not self._out_dir_edit.text():
            QMessageBox.warning(self, t("plugin_name"), t("output_dir_label"))
            return

        opts = self._build_options()
        collision_cb = self._collision_ask_callback if opts.collision_strategy == "ask" else None

        self._worker = ProjectConsolidator(
            layer_infos=self._layer_infos,
            options=opts,
            collision_callback=collision_cb,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        # UI lockdown
        self._btn_consolidate.setEnabled(False)
        self._btn_cancel.setText(t("btn_cancel"))
        self._progress_bar.setRange(0, len(self._layer_infos))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._progress_label.setVisible(True)
        self._log_box.setVisible(True)
        self._log_box.clear()

        # Run in thread
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.start()

    def _on_progress(self, current: int, total: int, message: str):
        self._progress_bar.setValue(current)
        self._progress_label.setText(message)

    def _on_finished(self, result: ConsolidationResult):
        self._result = result
        self._worker_thread.quit()

        n_ok = len(result.consolidated)
        n_err = len(result.errors)

        self._log_box.append(t("progress_done", n_ok))
        if n_err:
            self._log_box.append(t("progress_errors", n_err))
            for li in result.errors:
                self._log_box.append(f"  ✗ {li.layer_name}: {li.error_message}")
        for li in result.consolidated:
            self._log_box.append(f"  ✓ {li.layer_name}")

        self._progress_label.setText(t("progress_done", n_ok))
        self._btn_cancel.setText(t("btn_close"))
        self._btn_open.setVisible(True)

    def _on_error(self, message: str):
        self._worker_thread.quit()
        self._log_box.append(f"ERROR: {message}")
        self._btn_consolidate.setEnabled(True)
        self._btn_cancel.setText(t("btn_close"))

    def _on_cancel(self):
        if self._worker and self._worker_thread and self._worker_thread.isRunning():
            self._worker.cancel()
            self._worker_thread.quit()
            self._worker_thread.wait()
        self.reject()

    def _open_result_project(self):
        if self._result and self._result.output_project_path:
            from qgis.core import QgsProject
            QgsProject.instance().read(str(self._result.output_project_path))
        self.accept()

    # -----------------------------------------------------------------------
    # Collision ask callback
    # -----------------------------------------------------------------------

    def _collision_ask_callback(self, src_path: Path, dest_dir: Path):
        """Shows a dialog, returns (strategy_str, apply_all: bool)."""
        from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(t("collision_title"))
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(t("collision_msg", src_path.name, str(src_path), "")))

        bg = QButtonGroup(dlg)
        r_sub = QRadioButton(t("collision_use_subdir"))
        r_suf = QRadioButton(t("collision_use_suffix"))
        r_skip = QRadioButton(t("collision_skip"))
        r_sub.setChecked(True)
        bg.addButton(r_sub)
        bg.addButton(r_suf)
        bg.addButton(r_skip)
        layout.addWidget(r_sub)
        layout.addWidget(r_suf)
        layout.addWidget(r_skip)

        chk_all = QCheckBox(t("collision_apply_all"))
        layout.addWidget(chk_all)

        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(dlg.accept)
        layout.addWidget(bb)
        dlg.exec_()

        if r_sub.isChecked():
            choice = "subdir"
        elif r_suf.isChecked():
            choice = "suffix"
        else:
            choice = None  # skip
        return choice, chk_all.isChecked()
