# -*- coding: utf-8 -*-
"""
Internationalisation for Project Consolidator plugin.
Supported languages: en, de, cs
"""

STRINGS = {
    # --- General UI ---
    "plugin_name": {
        "en": "Project Consolidator",
        "de": "Projekt-Konsolidierer",
        "cs": "Konsolidátor projektu",
    },
    "language_label": {
        "en": "Language",
        "de": "Sprache",
        "cs": "Jazyk",
    },
    "btn_analyze": {
        "en": "Analyze Project",
        "de": "Projekt analysieren",
        "cs": "Analyzovat projekt",
    },
    "btn_consolidate": {
        "en": "Consolidate",
        "de": "Konsolidieren",
        "cs": "Konsolidovat",
    },
    "btn_cancel": {
        "en": "Cancel",
        "de": "Abbrechen",
        "cs": "Zrušit",
    },
    "btn_close": {
        "en": "Close",
        "de": "Schließen",
        "cs": "Zavřít",
    },
    "btn_open_project": {
        "en": "Open consolidated project",
        "de": "Konsolidierten Projekt öffnen",
        "cs": "Otevřít konsolidovaný projekt",
    },

    # --- Analysis dialog ---
    "analysis_title": {
        "en": "Project Consolidator – Analysis & Options",
        "de": "Projekt-Konsolidierer – Analyse & Optionen",
        "cs": "Konsolidátor projektu – Analýza & Možnosti",
    },
    "section_analysis": {
        "en": "Project Analysis",
        "de": "Projektanalyse",
        "cs": "Analýza projektu",
    },
    "section_output": {
        "en": "Output",
        "de": "Ausgabe",
        "cs": "Výstup",
    },
    "section_options": {
        "en": "Options",
        "de": "Optionen",
        "cs": "Možnosti",
    },
    "section_memory": {
        "en": "Memory Layers – Select layers to save",
        "de": "Memory-Layer – Layer zum Speichern auswählen",
        "cs": "Memory vrstvy – Vyberte vrstvy k uložení",
    },
    "section_services": {
        "en": "Service Layers (optional download)",
        "de": "Dienst-Layer (optionaler Download)",
        "cs": "Servisní vrstvy (volitelné stažení)",
    },
    "output_dir_label": {
        "en": "Output directory:",
        "de": "Ausgabeverzeichnis:",
        "cs": "Výstupní adresář:",
    },
    "output_dir_browse": {
        "en": "Browse…",
        "de": "Durchsuchen…",
        "cs": "Procházet…",
    },
    "opt_group_subdirs": {
        "en": "Preserve group folder structure",
        "de": "Gruppenstruktur als Unterordner erhalten",
        "cs": "Zachovat strukturu skupin jako podadresáře",
    },
    "opt_shp_to_gpkg": {
        "en": "Convert Shapefiles to GeoPackage (opt-in)",
        "de": "Shapefiles in GeoPackage konvertieren (optional)",
        "cs": "Konvertovat Shapefiles na GeoPackage (volitelně)",
    },
    "opt_collision_label": {
        "en": "Filename collision strategy:",
        "de": "Strategie bei Namenskollision:",
        "cs": "Strategie při kolizi názvů souborů:",
    },
    "collision_subdir": {
        "en": "Subdirectory by original path (default)",
        "de": "Unterordner nach Originalpfad (Standard)",
        "cs": "Podadresář dle původní cesty (výchozí)",
    },
    "collision_suffix": {
        "en": "Append numeric suffix (_2, _3, …)",
        "de": "Numerisches Suffix anhängen (_2, _3, …)",
        "cs": "Přidat číselnou příponu (_2, _3, …)",
    },
    "collision_ask": {
        "en": "Ask for each conflict",
        "de": "Bei jedem Konflikt fragen",
        "cs": "Dotázat se při každém konfliktu",
    },
    "opt_download_wfs": {
        "en": "Download WFS layers as GeoPackage",
        "de": "WFS-Layer als GeoPackage herunterladen",
        "cs": "Stáhnout WFS vrstvy jako GeoPackage",
    },
    "opt_download_wcs": {
        "en": "Download WCS layers as GeoTIFF",
        "de": "WCS-Layer als GeoTIFF herunterladen",
        "cs": "Stáhnout WCS vrstvy jako GeoTIFF",
    },
    "no_memory_layers": {
        "en": "No memory layers found in this project.",
        "de": "Keine Memory-Layer im Projekt gefunden.",
        "cs": "V projektu nebyly nalezeny žádné memory vrstvy.",
    },
    "no_service_layers": {
        "en": "No downloadable service layers found.",
        "de": "Keine herunterladbaren Dienst-Layer gefunden.",
        "cs": "Nebyly nalezeny žádné stažitelné servisní vrstvy.",
    },

    # --- Summary labels ---
    "summary_project": {
        "en": "Project",
        "de": "Projekt",
        "cs": "Projekt",
    },
    "summary_local_layers": {
        "en": "Local file layers",
        "de": "Lokale Datei-Layer",
        "cs": "Lokální souborové vrstvy",
    },
    "summary_memory_layers": {
        "en": "Memory layers",
        "de": "Memory-Layer",
        "cs": "Memory vrstvy",
    },
    "summary_service_layers": {
        "en": "Service layers (WMS/WFS/…)",
        "de": "Dienst-Layer (WMS/WFS/…)",
        "cs": "Servisní vrstvy (WMS/WFS/…)",
    },
    "summary_gpkg_files": {
        "en": "Unique GeoPackage files",
        "de": "Eindeutige GeoPackage-Dateien",
        "cs": "Unikátní GeoPackage soubory",
    },
    "summary_shp_files": {
        "en": "Shapefile sets",
        "de": "Shapefile-Sets",
        "cs": "Shapefile sady",
    },
    "summary_already_consolidated": {
        "en": "Already in Layers/",
        "de": "Bereits in Layers/",
        "cs": "Již v Layers/",
    },
    "summary_estimated_size": {
        "en": "Estimated copy size",
        "de": "Geschätzte Kopiergröße",
        "cs": "Odhadovaná velikost kopie",
    },

    # --- Progress dialog ---
    "progress_title": {
        "en": "Consolidating project…",
        "de": "Projekt wird konsolidiert…",
        "cs": "Konsoliduji projekt…",
    },
    "progress_copying": {
        "en": "Copying: {}",
        "de": "Kopiere: {}",
        "cs": "Kopíruji: {}",
    },
    "progress_saving_memory": {
        "en": "Saving memory layer: {}",
        "de": "Speichere Memory-Layer: {}",
        "cs": "Ukládám memory vrstvu: {}",
    },
    "progress_saving_project": {
        "en": "Saving consolidated project…",
        "de": "Konsolidiertes Projekt wird gespeichert…",
        "cs": "Ukládám konsolidovaný projekt…",
    },
    "progress_done": {
        "en": "Done! {} layers consolidated.",
        "de": "Fertig! {} Layer konsolidiert.",
        "cs": "Hotovo! {} vrstev konsolidováno.",
    },
    "progress_errors": {
        "en": "{} errors occurred. See log for details.",
        "de": "{} Fehler aufgetreten. Siehe Log für Details.",
        "cs": "Nastaly {} chyby. Viz log pro detaily.",
    },

    # --- Error messages ---
    "err_no_project": {
        "en": "No project is open. Please open or save a QGIS project first.",
        "de": "Kein Projekt geöffnet. Bitte öffnen oder speichern Sie zuerst ein QGIS-Projekt.",
        "cs": "Žádný projekt není otevřen. Nejprve otevřete nebo uložte QGIS projekt.",
    },
    "err_unsaved_project": {
        "en": "The project has not been saved yet. Please save it first (Ctrl+S).",
        "de": "Das Projekt wurde noch nicht gespeichert. Bitte zuerst speichern (Strg+S).",
        "cs": "Projekt ještě nebyl uložen. Nejprve jej uložte (Ctrl+S).",
    },
    "err_layer_invalid_after": {
        "en": "Layer '{}' became invalid after source update. Reverting.",
        "de": "Layer '{}' ist nach Quellaktualisierung ungültig geworden. Wird zurückgesetzt.",
        "cs": "Vrstva '{}' se stala neplatnou po aktualizaci zdroje. Vrácení zpět.",
    },
    "err_copy_failed": {
        "en": "Failed to copy '{}': {}",
        "de": "Kopieren von '{}' fehlgeschlagen: {}",
        "cs": "Kopírování '{}' selhalo: {}",
    },

    # --- Collision dialog ---
    "collision_title": {
        "en": "Filename Conflict",
        "de": "Namenskonflikt",
        "cs": "Konflikt názvů souborů",
    },
    "collision_msg": {
        "en": "File '{}' already exists at destination.\nOriginal: {}\nHow to resolve?",
        "de": "Datei '{}' existiert bereits im Zielordner.\nOriginal: {}\nWie auflösen?",
        "cs": "Soubor '{}' již v cílovém adresáři existuje.\nOriginal: {}\nJak řešit?",
    },
    "collision_use_subdir": {
        "en": "Use subdirectory",
        "de": "Unterordner verwenden",
        "cs": "Použít podadresář",
    },
    "collision_use_suffix": {
        "en": "Add numeric suffix",
        "de": "Numerisches Suffix",
        "cs": "Přidat číselnou příponu",
    },
    "collision_skip": {
        "en": "Skip this layer",
        "de": "Diesen Layer überspringen",
        "cs": "Přeskočit tuto vrstvu",
    },
    "collision_apply_all": {
        "en": "Apply to all conflicts",
        "de": "Auf alle Konflikte anwenden",
        "cs": "Aplikovat na všechny konflikty",
    },
}


class I18n:
    """Simple translation helper. Default language: English."""

    _instance = None
    _lang = "en"

    @classmethod
    def set_language(cls, lang: str):
        lang = lang.lower().strip()
        # Accept 'cs', 'cz', 'czech' all as Czech
        if lang in ("cz", "czech", "cs"):
            lang = "cs"
        if lang not in ("en", "de", "cs"):
            lang = "en"
        cls._lang = lang

    @classmethod
    def get_language(cls) -> str:
        return cls._lang

    @classmethod
    def t(cls, key: str, *args) -> str:
        """Translate key, optionally format with args."""
        entry = STRINGS.get(key)
        if entry is None:
            return f"[{key}]"
        text = entry.get(cls._lang, entry.get("en", f"[{key}]"))
        if args:
            try:
                text = text.format(*args)
            except (IndexError, KeyError):
                pass
        return text


# Module-level shortcut
t = I18n.t
