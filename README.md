# Agentic-Intelligence-Research

Dieses Repository enthält Workflows und Komponenten für agentenbasierte Prozessautomatisierung (z. B. rund um Google Calendar, Event Handling, Logging, Kommunikation).

## Struktur

- `agents/`: Zentrale Agenten (z.B. E-Mail-Agent)
- `logs/`: Logging-Module für Events, Workflows etc.
- `templates/`: Zentrale Templates für E-Mails und weitere Kommunikation
- `utils/`: Utility-Module (Konfiguration, etc.)
- `polling/`, `extraction/`, `human_in_the_loop/`, `reminders/`: Platzhalter für geplante Erweiterungen
- `tests/`: Unit Tests und Test-Skripte

## Umgebungskonfiguration

### SMTP-Konfiguration für E-Mail-Funktionen

Das Projekt nutzt Umgebungsvariablen für die SMTP-Konfiguration. Dies ermöglicht eine sichere Konfiguration sowohl für lokale Entwicklung als auch für CI/CD.

#### Lokale Entwicklung (.env-Datei)

1. Kopieren Sie `.env.example` zu `.env`:
   ```bash
   cp .env.example .env
   ```

2. Bearbeiten Sie die `.env`-Datei und tragen Sie Ihre SMTP-Credentials ein:
   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=ihr-email@example.com
   SMTP_PASS=ihr-app-passwort
   SMTP_SECURE=false
   MAIL_FROM=ihr-email@example.com
   ```

3. Installieren Sie optional `python-dotenv` für automatisches Laden der .env-Datei:
   ```bash
   pip install python-dotenv
   ```

#### CI/CD und Produktionsumgebung (GitHub Secrets)

Für GitHub Actions oder andere CI/CD-Systeme, setzen Sie die folgenden Secrets/Umgebungsvariablen:

- `SMTP_HOST`: SMTP-Server (z.B. smtp.gmail.com)
- `SMTP_PORT`: SMTP-Port (587 für STARTTLS, 465 für SSL)
- `SMTP_USER`: SMTP-Benutzername/E-Mail-Adresse
- `SMTP_PASS`: SMTP-Passwort oder App-Passwort
- `SMTP_SECURE`: true für SSL (Port 465), false für STARTTLS (Port 587)
- `MAIL_FROM`: Absender-E-Mail-Adresse

#### Verwendung im Code

```python
from agents.email_agent import EmailAgent

# E-Mail-Agent mit Umgebungsvariablen erstellen
agent = EmailAgent.from_env()
agent.send_email("empfaenger@example.com", "Betreff", "Nachricht")
```

#### Wichtige Hinweise

- **Niemals** echte Credentials in den Code committen
- Die `.env`-Datei ist bereits in `.gitignore` und wird nicht versioniert
- Für Gmail: Verwenden Sie App-Passwörter statt Ihres normalen Passworts
- Für Outlook: Verwenden Sie Ihr E-Mail-Passwort oder App-Passwort bei aktivierter 2FA

Weitere Dokumentation folgt mit wachsendem Funktionsumfang.
