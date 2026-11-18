"""SRI assessments imported from other tools (EDISON JSON format, see tools/eu_excel_to_json.py).

Draft: every import method loads the preset ARV Voldsløkka assessment (EU calculation sheet v4.5, Method B).
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXAMPLE_FILE = DATA_DIR / "arv_voldslokka_2025.json"

IMPORT_METHODS = {
    "json": "EDISON SRI assessment (JSON file)",
    "eu_excel": "EU SRI calculation sheet (Excel, version 4.5)",
    "sri_norsk": "SRI Norsk (export from the web tool)",
}
SRI_NORSK_URL = "https://sri.minder.no/"


@lru_cache(maxsize=1)
def load_example() -> dict:
    """The preset assessment used by the draft for every import method."""
    return json.loads(EXAMPLE_FILE.read_text(encoding="utf-8"))


def import_assessment(method: str, contents: str | None = None, filename: str | None = None) -> dict:
    """Import an assessment. DRAFT: ignores the uploaded file and returns the ARV example.

    Later: parse `contents` (base64 from dcc.Upload) according to `method`
    (JSON → validate; EU Excel → tools/eu_excel_to_json.convert; SRI Norsk → its export format).
    """
    if method not in IMPORT_METHODS:
        raise ValueError(f"Unknown import method: {method}")
    data = dict(load_example())
    data["imported_with"] = method
    data["uploaded_file"] = filename
    return data
