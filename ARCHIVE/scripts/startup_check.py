"""Archived environment validation script retained for reference.

Modern deployments rely on standard dependency management and CI checks, so
this standalone bootstrap verification is no longer invoked by the runtime.
"""

import os
import sys
from dotenv import load_dotenv

# .env laden (bei Bedarf kannst du einen Pfad angeben, z.B. load_dotenv(dotenv_path="path/to/.env"))
load_dotenv()

REQUIRED_SECRETS = [
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_PROJECT_ID",
    "GOOGLE_AUTH_URI",
    "GOOGLE_TOKEN_URI",
    "GOOGLE_AUTH_PROVIDER_X509_CERT_URL",
    "GOOGLE_REDIRECT_URIS",
    "GOOGLE_REFRESH_TOKEN",
    "IMAP_HOST",
    "IMAP_PORT",
    "IMAP_USER",
    "IMAP_PASS",
    "IMAP_FOLDER",
    "MAIL_FROM",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASS",
    "SMTP_SECURE",
    "SENDER_EMAIL",
    "OPENAI_API_KEY",
]

REQUIRED_VARIABLES = [
    "CAL_LOOKAHEAD_DAYS",
    "CAL_LOOKBACK_DAYS",
    "GOOGLE_CALENDAR_IDS",
]

# Optional, falls du Hubspot und weitere Dienste nutzt:
OPTIONAL_SECRETS = [
    "HUBSPOT_ACCESS_TOKEN",
    "HUBSPOT_CLIENT_SECRET",
]
OPTIONAL_VARIABLES = [
    "HUBSPOT_SCOPES",
    "LOG_STORAGE_DIR",
]


def check_env_vars(var_names, section="ENV"):
    missing = []
    for name in var_names:
        if not os.environ.get(name):
            missing.append(name)
    if missing:
        print(f"[ERROR] {section}: Fehlende Variablen: {', '.join(missing)}")
    else:
        print(f"[OK] {section}: Alle Variablen gesetzt.")
    return missing


def main():
    print("=== Startup Check: Agentic Intelligence Research ===\n")

    missing_secrets = check_env_vars(REQUIRED_SECRETS, "SECRETS")
    missing_vars = check_env_vars(REQUIRED_VARIABLES, "VARIABLES")

    if missing_secrets or missing_vars:
        print("\n[FAILED] Startup Check nicht bestanden.")
        sys.exit(1)
    else:
        print("\n[OK] Startup Check bestanden! System ist bereit für den Live-Lauf.")

    # Optionale Felder prüfen (nur Hinweis, nicht kritisch)
    check_env_vars(OPTIONAL_SECRETS, "OPTIONAL SECRETS")
    check_env_vars(OPTIONAL_VARIABLES, "OPTIONAL VARIABLES")


if __name__ == "__main__":
    main()
