"""UI strings for mass_bitrate_gui (German / English)."""

from __future__ import annotations

from typing import Dict, Tuple

LANG_DE = "de"
LANG_EN = "en"
LANG_CODES: Tuple[str, ...] = (LANG_DE, LANG_EN)

# Flat key -> per-language string. Use str.format(**kwargs) where placeholders exist.
STRINGS: Dict[str, Dict[str, str]] = {
    LANG_DE: {
        "app_title": "Massen-Bitrate-Änderung",
        "lf_folders": "Ordner",
        "lbl_input_folder": "Input-Ordner",
        "lbl_output_folder": "Output-Ordner",
        "btn_browse": "Wählen",
        "btn_auto_output": "Auto = input/_converted",
        "chk_output_beside_source": "Ausgabe im Quellordner",
        "lf_rename": "Namen bereinigen (_bitrate)",
        "btn_preview": "Vorschau",
        "btn_rename": "Umbenennen",
        "chk_rename_video_only": "Nur Video-Endungen",
        "lf_options": "Optionen",
        "lbl_language": "Sprache",
        "lang_de": "Deutsch",
        "lang_en": "English",
        "chk_recursive": "Unterordner einbeziehen",
        "chk_only_lower": "Nur wenn kleiner (sonst skip)",
        "lbl_video_codec": "Video-Codec",
        "lbl_audio": "Audio",
        "lbl_suffix": "Suffix",
        "chk_output_mp4": "Ausgabe .mp4",
        "chk_strip_bitrate": "Nach Erfolg: _bitrate aus Dateiname entfernen",
        "lbl_after_success": "Nach Erfolg",
        "lf_rules": "Bitrate-Regeln nach Auflösung (kbps)",
        "lbl_preset": "Preset",
        "btn_load_preset": "Preset laden",
        "lbl_new_preset": "Als eigenes Preset speichern",
        "btn_save_preset": "Speichern",
        "lbl_rule_kbps": "kbps",
        "btn_scan": "Ordner scannen",
        "btn_scan_busy": "Scanne…",
        "btn_start": "Konvertierung starten",
        "btn_stop": "Stop",
        "th_file": "Datei",
        "th_resolution": "Auflösung",
        "th_source": "Original kbps",
        "th_rule": "Regel kbps",
        "th_target": "Ziel kbps",
        "th_est_out": "Est. Out MB",
        "th_save": "Est. Save MB",
        "th_save_pct": "Est. Save %",
        "th_action": "Aktion",
        "th_reason": "Grund",
        "mnu_explorer_file": "Datei im Explorer markieren",
        "mnu_explorer_folder": "Ordner im Explorer öffnen",
        "status_ready": "Bereit.",
        "jobs_fmt": "Konvertierung: {cur}/{tot}",
        "dlg_suffix_title": "Suffix",
        "dlg_suffix_body": (
            "Suffix wird an den Dateinamen vor der Endung angehängt.\n\n"
            "- Leeres Feld: kein Suffix.\n"
            "- Ausnahme: wenn Input-Ordner und Output-Ordner gleich sind und das Feld leer ist, "
            "wird automatisch der Suffix _bitrate gesetzt (Überschreiben vermeiden).\n\n"
            "Beispiel: video.flv + Suffix _neu -> video_neu.flv\n\n"
            "Optional: Checkbox „Nach Erfolg: _bitrate aus Dateiname entfernen“ benennt fertige Outputs "
            "von …_bitrate.ext nach ….ext um, aber nur wenn dadurch keine bestehende Datei überschrieben wird."
        ),
        "dlg_rename_title": "Namen bereinigen (_bitrate)",
        "dlg_rename_body": (
            "Entfernt ein trailing „*_bitrate“ im Dateinamen (nur die Endung „_bitrate“), "
            "und nur wenn das Ziel noch nicht existiert.\n\n"
            "Nach Umbenennung nochmal „Ordner scannen“. Sonst stimmen die Pfade in der Liste nicht."
        ),
        "dlg_output_beside_title": "Ausgabe im Quellordner",
        "dlg_output_beside_body": (
            "Wenn aktiv, ist der Output-Ordner gleich dem Input-Ordner.\n\n"
            "Die Ausgabedateien landen dann in denselben Unterordnern wie die Quellen "
            "(relativ zum gewählten Input-Root).\n\n"
            "Hinweis: Wenn Ausgabe und Quelle denselben Dateinamen hätten, schreibt das Tool "
            "temporär in eine .partial-Datei und ersetzt erst nach erfolgreicher Prüfung.\n\n"
            "Für FLV -> MP4 (anderes Suffix) reicht oft ein leerer Suffix, damit der Basisname gleich bleibt."
        ),
        "dlg_post_title": "Nach erfolgreicher Konvertierung",
        "dlg_post_body": (
            "Hier steuert du, was mit der Originaldatei passiert, NACHDEM ffmpeg sauber war "
            "und die Ausgabedatei verifiziert wurde.\n\n"
            "- keep: Original bleibt unverändert.\n"
            "- move_to_backup: Original wird nach OUTPUT/_original_backup/… verschoben "
            "(gleiche Unterordnerstruktur). Empföhlen für große Batches.\n"
            "- delete_original: Original wird gelöscht. Nur nutzen, wenn du dir absolut sicher bist.\n\n"
            "Empfehlung: move_to_backup statt direkt löschen."
        ),
        "err_rule_empty": "Leerer Wert bei Regel {threshold}p.",
        "err_rule_invalid": "Ungültiger Wert bei Regel {threshold}p: {raw}",
        "err_rule_positive": "Regel {threshold}p muss > 0 sein.",
        "dlg_error": "Fehler",
        "dlg_busy": "Läuft",
        "dlg_rule_error": "Regelfehler",
        "status_preset_loaded": "Preset geladen: {name}",
        "dlg_preset": "Preset",
        "err_preset_name_empty": "Bitte Namen für eigenes Preset eingeben.",
        "err_preset_builtin": "Dieser Name ist reserviert (Built-in). Bitte anderen Namen nehmen.",
        "status_preset_saved": "Eigenes Preset gespeichert: {name}",
        "dlg_explorer": "Explorer",
        "err_file_not_found": "Datei wurde nicht gefunden.",
        "err_folder_not_found": "Ordner wurde nicht gefunden.",
        "reason_resolution": "Auflösung nicht lesbar",
        "reason_bitrate_unknown": "Original-Bitrate unbekannt",
        "reason_no_gain": "Regel >= Original (kein Gewinn)",
        "reason_reduce": "Reduzieren",
        "reason_scan_error": "Scanfehler",
        "tbl_action_skip": "skip",
        "tbl_action_convert": "convert",
        "dlg_input_title": "Input-Ordner wählen",
        "dlg_output_title": "Output-Ordner wählen",
        "err_input_required": "Bitte Input-Ordner auswählen.",
        "err_output_required": "Bitte Output-Ordner auswählen.",
        "err_input_missing": "Input-Ordner existiert nicht.",
        "info_scan_running": "Scan läuft bereits.",
        "status_scanning": "Scanne Videos…",
        "status_no_videos": "Keine Videodateien gefunden.",
        "info_convert_running": "Konvertierung läuft bereits.",
        "err_scan_first": "Bitte zuerst scannen.",
        "status_convert_start": "Starte Konvertierung…",
        "status_stop_requested": "Stop angefordert …",
        "status_rename_skip": "Umbenennen übersprungen (Ziel existiert): {name}",
        "preview_scanned": "Gescannt: {n}",
        "preview_renamable": "Umbenennbar: {n}",
        "preview_skipped": "Übersprungen (Konflikt / nicht möglich): {n}",
        "preview_more": "… und {n} weitere",
        "dlg_preview_title": "Vorschau: `_bitrate` entfernen",
        "info_wait_convert": "Bitte warten: Konvertierung läuft.",
        "err_input_set": "Bitte Input-Ordner setzen.",
        "info_rename_running": "Umbenennung läuft bereits.",
        "dlg_rename_none": "Umbenennen",
        "info_rename_none_body": "Nichts zu tun (keine passenden Dateien).",
        "dlg_rename_confirm_title": "Umbenennen bestätigen",
        "dlg_rename_confirm_body": "\n\nJetzt wirklich umbenennen?",
        "status_rename_progress": "Umbenennen: {cur}/{total}",
        "status_rename_done": "Umbenennen fertig: ok={ok}, fehler={err}, übersprungen_vorher={conflicts}",
        "done_no_convert": "Keine Dateien zum Konvertieren (nur skip).",
        "done_aborted": "Abgebrochen. Fertig: {done}, Fehler: {failed}, Backup: {moved}, Gelöscht: {deleted}",
        "status_converting": "Konvertiere: {name} -> {kbps} kbps",
        "err_unknown_ffmpeg": "Unbekannter ffmpeg Fehler",
        "status_err_file": "Fehler bei {name}: {detail}",
        "status_verify_fail": "Fehler bei {name}: Output-Verifikation fehlgeschlagen",
        "status_post_fail": "Nachbearbeitung fehlgeschlagen bei {name}: {detail}",
        "done_summary": (
            "Fertig. Erfolgreich: {done}, Fehler: {failed}, Backup: {moved}, Gelöscht: {deleted}, "
            "Nachbearbeitung-Fehler: {post_failed}"
        ),
        "status_scan_progress": "Scanne Videos… {cur}/{total}",
        "status_building_list": "Liste wird aufgebaut… ({n} Dateien)",
        "status_scan_error": "Scanfehler: {detail}",
        "scan_done_summary": (
            "Scan fertig: {files} Dateien, convert={conv}, skip={skip} | "
            "Est. Save: {mb} MB ({pct:.1f}%)"
        ),
        "dlg_ffmpeg_missing_title": "ffmpeg/ffprobe fehlt",
        "dlg_ffmpeg_missing_body": (
            "Bitte ffmpeg und ffprobe installieren und in PATH eintragen.\n"
            "Danach dieses Tool erneut starten."
        ),
    },
    LANG_EN: {
        "app_title": "Mass Bitrate Changer",
        "lf_folders": "Folders",
        "lbl_input_folder": "Input folder",
        "lbl_output_folder": "Output folder",
        "btn_browse": "Browse…",
        "btn_auto_output": "Auto = input/_converted",
        "chk_output_beside_source": "Output next to source",
        "lf_rename": "Clean up names (_bitrate)",
        "btn_preview": "Preview",
        "btn_rename": "Rename",
        "chk_rename_video_only": "Video extensions only",
        "lf_options": "Options",
        "lbl_language": "Language",
        "lang_de": "German",
        "lang_en": "English",
        "chk_recursive": "Include subfolders",
        "chk_only_lower": "Only if lower bitrate (else skip)",
        "lbl_video_codec": "Video codec",
        "lbl_audio": "Audio",
        "lbl_suffix": "Suffix",
        "chk_output_mp4": "Force .mp4 output",
        "chk_strip_bitrate": "On success: remove _bitrate from filename",
        "lbl_after_success": "After success",
        "lf_rules": "Bitrate rules by resolution (kbps)",
        "lbl_preset": "Preset",
        "btn_load_preset": "Load preset",
        "lbl_new_preset": "Save as custom preset",
        "btn_save_preset": "Save",
        "lbl_rule_kbps": "kbps",
        "btn_scan": "Scan folder",
        "btn_scan_busy": "Scanning…",
        "btn_start": "Start conversion",
        "btn_stop": "Stop",
        "th_file": "File",
        "th_resolution": "Resolution",
        "th_source": "Source kbps",
        "th_rule": "Rule kbps",
        "th_target": "Target kbps",
        "th_est_out": "Est. out MB",
        "th_save": "Est. save MB",
        "th_save_pct": "Est. save %",
        "th_action": "Action",
        "th_reason": "Reason",
        "mnu_explorer_file": "Reveal file in Explorer",
        "mnu_explorer_folder": "Open folder in Explorer",
        "status_ready": "Ready.",
        "jobs_fmt": "Conversion: {cur}/{tot}",
        "dlg_suffix_title": "Suffix",
        "dlg_suffix_body": (
            "The suffix is inserted before the file extension.\n\n"
            "- Empty field: no suffix.\n"
            "- Exception: if input and output folders are the same and the field is empty, "
            "the suffix _bitrate is applied automatically (to avoid overwriting).\n\n"
            "Example: video.flv + suffix _new -> video_new.flv\n\n"
            "Optional: the checkbox “On success: remove _bitrate from filename” renames finished outputs "
            "from …_bitrate.ext to ….ext only if no existing file would be overwritten."
        ),
        "dlg_rename_title": "Clean up names (_bitrate)",
        "dlg_rename_body": (
            "Removes a trailing “*_bitrate” in the file name (only the “_bitrate” ending), "
            "and only if the target name does not already exist.\n\n"
            "After renaming, run “Scan folder” again so paths in the list stay correct."
        ),
        "dlg_output_beside_title": "Output next to source",
        "dlg_output_beside_body": (
            "When enabled, the output folder equals the input folder.\n\n"
            "Encoded files are written beside the sources using the same subfolder layout "
            "(relative to the selected input root).\n\n"
            "Note: if source and output would share the same path, the tool writes a temporary "
            ".partial file first and only replaces the target after verification.\n\n"
            "For FLV -> MP4 (different extension), an empty suffix is often enough to keep the base name."
        ),
        "dlg_post_title": "After successful conversion",
        "dlg_post_body": (
            "Controls what happens to the original file AFTER ffmpeg finished successfully "
            "and the output file was verified.\n\n"
            "- keep: original stays unchanged.\n"
            "- move_to_backup: original is moved to OUTPUT/_original_backup/… "
            "(same subfolder layout). Recommended for large batches.\n"
            "- delete_original: original is deleted. Only if you are absolutely sure.\n\n"
            "Recommendation: move_to_backup instead of deleting outright."
        ),
        "err_rule_empty": "Empty value for rule {threshold}p.",
        "err_rule_invalid": "Invalid value for rule {threshold}p: {raw}",
        "err_rule_positive": "Rule {threshold}p must be > 0.",
        "dlg_error": "Error",
        "dlg_busy": "Busy",
        "dlg_rule_error": "Rule error",
        "status_preset_loaded": "Preset loaded: {name}",
        "dlg_preset": "Preset",
        "err_preset_name_empty": "Please enter a name for the custom preset.",
        "err_preset_builtin": "This name is reserved (built-in). Please choose another name.",
        "status_preset_saved": "Custom preset saved: {name}",
        "dlg_explorer": "Explorer",
        "err_file_not_found": "File was not found.",
        "err_folder_not_found": "Folder was not found.",
        "reason_resolution": "Could not read resolution",
        "reason_bitrate_unknown": "Source bitrate unknown",
        "reason_no_gain": "Rule >= source (no gain)",
        "reason_reduce": "Reduce",
        "reason_scan_error": "Scan error",
        "tbl_action_skip": "skip",
        "tbl_action_convert": "convert",
        "dlg_input_title": "Choose input folder",
        "dlg_output_title": "Choose output folder",
        "err_input_required": "Please choose an input folder.",
        "err_output_required": "Please choose an output folder.",
        "err_input_missing": "Input folder does not exist.",
        "info_scan_running": "A scan is already running.",
        "status_scanning": "Scanning videos…",
        "status_no_videos": "No video files found.",
        "info_convert_running": "Conversion is already running.",
        "err_scan_first": "Please scan first.",
        "status_convert_start": "Starting conversion…",
        "status_stop_requested": "Stop requested …",
        "status_rename_skip": "Rename skipped (target exists): {name}",
        "preview_scanned": "Scanned: {n}",
        "preview_renamable": "Renamable: {n}",
        "preview_skipped": "Skipped (conflict / not possible): {n}",
        "preview_more": "… and {n} more",
        "dlg_preview_title": "Preview: remove `_bitrate`",
        "info_wait_convert": "Please wait: conversion is running.",
        "err_input_set": "Please set the input folder.",
        "info_rename_running": "Rename is already running.",
        "dlg_rename_none": "Rename",
        "info_rename_none_body": "Nothing to do (no matching files).",
        "dlg_rename_confirm_title": "Confirm rename",
        "dlg_rename_confirm_body": "\n\nRename now?",
        "status_rename_progress": "Renaming: {cur}/{total}",
        "status_rename_done": "Rename finished: ok={ok}, errors={err}, skipped_before={conflicts}",
        "done_no_convert": "No files to convert (all skipped).",
        "done_aborted": "Aborted. Done: {done}, errors: {failed}, backup: {moved}, deleted: {deleted}",
        "status_converting": "Converting: {name} -> {kbps} kbps",
        "err_unknown_ffmpeg": "Unknown ffmpeg error",
        "status_err_file": "Error for {name}: {detail}",
        "status_verify_fail": "Error for {name}: output verification failed",
        "status_post_fail": "Post-processing failed for {name}: {detail}",
        "done_summary": (
            "Finished. OK: {done}, errors: {failed}, backup: {moved}, deleted: {deleted}, "
            "post-processing errors: {post_failed}"
        ),
        "status_scan_progress": "Scanning videos… {cur}/{total}",
        "status_building_list": "Building list… ({n} files)",
        "status_scan_error": "Scan error: {detail}",
        "scan_done_summary": (
            "Scan done: {files} files, convert={conv}, skip={skip} | "
            "Est. save: {mb} MB ({pct:.1f}%)"
        ),
        "dlg_ffmpeg_missing_title": "ffmpeg/ffprobe missing",
        "dlg_ffmpeg_missing_body": (
            "Please install ffmpeg and ffprobe and add them to PATH.\n"
            "Then restart this tool."
        ),
    },
}


def tr(lang: str, key: str, **kwargs: object) -> str:
    lang = lang if lang in LANG_CODES else LANG_DE
    s = STRINGS.get(lang, {}).get(key)
    if s is None:
        s = STRINGS[LANG_DE].get(key, key)
    if kwargs:
        return s.format(**kwargs)
    return s
