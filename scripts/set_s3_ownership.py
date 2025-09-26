"""Deprecated helper – S3 ownership management is no longer required."""

def main() -> None:
    raise SystemExit(
        "S3 ownership configuration has been disabled. Logs are persisted locally in PostgreSQL."
    )


if __name__ == "__main__":
    main()

