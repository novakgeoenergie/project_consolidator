# -*- coding: utf-8 -*-
"""
Project Consolidator – QGIS Plugin
Required by QGIS plugin loader.
"""


def classFactory(iface):
    from .project_consolidator import ProjectConsolidatorPlugin
    return ProjectConsolidatorPlugin(iface)
