# -*- coding: utf-8 -*-
"""
Project Consolidator – QGIS Plugin
Entry point: registered via __init__.py classFactory().

Menu placement: Plugins → Project Consolidator
Toolbar:        Project Consolidator toolbar
"""

from __future__ import annotations

import os
from qgis.core import QgsProject
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QToolBar

from .i18n import I18n, t

PLUGIN_NAME = "Project Consolidator"
TOOLBAR_TITLE = "Project Consolidator"


def _find_or_create_toolbar(main_window, title: str) -> QToolBar:
    """Return an existing toolbar named *title*, or create and dock it."""
    for tb in main_window.findChildren(QToolBar):
        if tb.windowTitle() == title:
            return tb
    tb = QToolBar(title, main_window)
    tb.setObjectName(f"toolbar_{title.replace(' ', '_')}")
    main_window.addToolBar(tb)
    return tb


class ProjectConsolidatorPlugin:
    """QGIS Plugin main class."""

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.plugin_dir = os.path.dirname(__file__)
        self._action: QAction | None = None
        self._toolbar: QToolBar | None = None

        # Load saved language preference
        settings = QSettings()
        lang = settings.value("project_consolidator/language", "en")
        I18n.set_language(lang)

    # -----------------------------------------------------------------------
    # QGIS lifecycle
    # -----------------------------------------------------------------------

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "resources", "icon.svg")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self._action = QAction(icon, t("plugin_name"), self.iface.mainWindow())
        self._action.setToolTip(t("plugin_name"))
        self._action.triggered.connect(self.run)

        # ── Plugins menu ─────────────────────────────────────────────────────
        # Registers under Plugins → Project Consolidator (standard QGIS pattern)
        self.iface.addPluginToMenu(PLUGIN_NAME, self._action)

        # ── Project Consolidator toolbar ─────────────────────────────────────
        self._toolbar = _find_or_create_toolbar(
            self.iface.mainWindow(), TOOLBAR_TITLE
        )
        self._toolbar.addAction(self._action)

    def unload(self):
        if self._action:
            if self._toolbar:
                self._toolbar.removeAction(self._action)
                if not self._toolbar.actions():
                    self.iface.mainWindow().removeToolBar(self._toolbar)

            # Remove from Plugins menu
            self.iface.removePluginMenu(PLUGIN_NAME, self._action)

            del self._action
            self._action = None

    # -----------------------------------------------------------------------
    # Run
    # -----------------------------------------------------------------------

    def run(self):
        project = QgsProject.instance()

        if not project.fileName():
            QMessageBox.warning(
                self.iface.mainWindow(),
                t("plugin_name"),
                t("err_unsaved_project"),
            )
            return

        from .dialogs.analysis_dialog import AnalysisDialog
        dlg = AnalysisDialog(parent=self.iface.mainWindow())
        dlg.exec_()

        # Persist language choice
        settings = QSettings()
        settings.setValue("project_consolidator/language", I18n.get_language())
