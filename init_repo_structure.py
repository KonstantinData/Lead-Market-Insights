import os

folders = [
    "agents",
    "logs",
    "log_storage",
    "templates",
    "polling",
    "extraction",
    "human_in_the_loop",
    "reminders",
    "tests",
]

# Platzhalterdateien, damit die Ordner im Repo bleiben
placeholders = {
    "agents/.gitkeep": "",
    "logs/.gitkeep": "",
    "log_storage/.gitkeep": "",
    "templates/.gitkeep": "",
    "tests/__init__.py": "# Test-Modul-Initialisierung\n",
    "polling/README.md": (
        "Platzhalter für Trigger-/Polling-Logik.\n"
        "Hier entsteht die Anbindung für wiederkehrende Prüfungen oder externe Trigger.\n"
    ),
    "extraction/README.md": (
        "Platzhalter für zukünftige Extraktions- und Parsing-Logik.\n"
        "Hier werden Module zur Datenextraktion ergänzt.\n"
    ),
    "human_in_the_loop/README.md": (
        "Platzhalter für Human-in-the-Loop-Komponenten.\n"
        "Hier entsteht später z.B. die Integration für manuelle Freigaben oder Rückfragen.\n"
    ),
    "reminders/README.md": (
        "Platzhalter für Reminder- und Eskalations-Workflows.\n"
        "Hier werden Module für Erinnerungen, automatische Folgeaktionen etc. ergänzt.\n"
    ),
    "README.md": (
        "# Agentic-Intelligence-Research\n\n"
        "Dieses Repository enthält Workflows und Komponenten für agentenbasierte Prozessautomatisierung "
        "(z. B. rund um Google Calendar, Event Handling, Logging, Kommunikation).\n\n"
        "## Struktur\n\n"
        "- `agents/`: Zentrale Agenten (z.B. E-Mail-Agent)\n"
        "- `logs/`: Logging-Module für Events, Workflows etc.\n"
        "- `templates/`: Zentrale Templates für E-Mails und weitere Kommunikation\n"
        "- `polling/`, `extraction/`, `human_in_the_loop/`, `reminders/`: Platzhalter für geplante Erweiterungen\n"
        "- `tests/`: Unit Tests und Test-Skripte\n\n"
        "Weitere Dokumentation folgt mit wachsendem Funktionsumfang.\n"
    ),
}


def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)


def main():
    for folder in folders:
        ensure_folder(folder)
    for rel_path, content in placeholders.items():
        folder = os.path.dirname(rel_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        with open(rel_path, "w", encoding="utf-8") as f:
            f.write(content)


if __name__ == "__main__":
    main()
