#!/usr/bin/env python3
"""
Bulk Import Translations
========================
Reads a JSON file (translations_import.json) and imports all translations
into the SQLite database (translations.db).

Usage:
    python seed_translations.py

JSON Format Example:
{
    "en": { "key.name": "Value" },
    "th": { "key.name": "ค่า" }
}
"""

import sqlite3
import os
import json
import sys

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
I18N_DIR = os.path.join(
    SCRIPT_DIR, "..", "..", "x01-FrontEnd", "x0101-xMixing_Nuxt",
    "app", "i18n"
)
DB_PATH = os.path.join(I18N_DIR, "translations.db")
IMPORT_PATH = os.path.join(I18N_DIR, "translations_import.json")


def seed_database(translations: dict):
    """Insert translations into SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            locale TEXT NOT NULL DEFAULT 'en',
            value TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(key, locale)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_translations_locale
        ON translations(locale)
    """)

    total = 0
    for locale in ["en", "th"]:
        if locale in translations:
            pairs = translations[locale]
            for key, value in pairs.items():
                conn.execute("""
                    INSERT INTO translations (key, locale, value, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key, locale)
                    DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """, (key, locale, value))
                total += 1

    conn.commit()

    # Stats
    en_count = conn.execute("SELECT COUNT(*) FROM translations WHERE locale='en'").fetchone()[0]
    th_count = conn.execute("SELECT COUNT(*) FROM translations WHERE locale='th'").fetchone()[0]
    conn.close()

    return total, en_count, th_count


def main():
    print("=" * 60)
    print("  Bulk Import Translations")
    print("=" * 60)

    # Check import file exists
    if not os.path.exists(IMPORT_PATH):
        print(f"❌ Import file not found: {IMPORT_PATH}")
        print(f"👉 Please create this file with your translations in JSON format.")
        sys.exit(1)

    print(f"📖 Reading: {IMPORT_PATH}")
    try:
        with open(IMPORT_PATH, "r", encoding="utf-8") as f:
            translations = json.load(f)
    except Exception as e:
        print(f"❌ Error parsing JSON: {e}")
        sys.exit(1)

    en_keys = len(translations.get("en", {}))
    th_keys = len(translations.get("th", {}))
    print(f"   EN keys found: {en_keys}")
    print(f"   TH keys found: {th_keys}")

    if en_keys == 0 and th_keys == 0:
        print("❌ No translations found in JSON!")
        sys.exit(1)

    print(f"\n💾 Writing to: {os.path.abspath(DB_PATH)}")
    total, en_count, th_count = seed_database(translations)

    print(f"\n✅ Done!")
    print(f"   Total upserted: {total}")
    print(f"   EN in DB: {en_count}")
    print(f"   TH in DB: {th_count}")
    print(f"\n📂 Database file: {os.path.abspath(DB_PATH)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
