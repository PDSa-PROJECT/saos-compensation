"""Shared configuration and source fixtures without inference or network access."""

from pathlib import Path
import os
import shutil

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolate_runtime_sources(monkeypatch, tmp_path):
    """Keep tests independent of developer runtime variables and the real .env.

    args:
        monkeypatch: Scoped environment and settings-policy replacements.
        tmp_path: Temporary root for a missing test dotenv file.

    returns:
        None.
    """
    from saos_dataset.settings import RuntimeSettings

    for name in tuple(os.environ):
        if name.lower() in RuntimeSettings.model_fields:
            monkeypatch.delenv(name)
    monkeypatch.setitem(RuntimeSettings.model_config, "env_file", tmp_path / "root.env")


@pytest.fixture(scope="session")
def project_root():
    """Locate project configuration and fixtures independently of test nesting.

    args:
        None.

    returns:
        Repository root directory.
    """
    return PROJECT_ROOT


@pytest.fixture
def config_directory(tmp_path, project_root):
    """Copy processing settings into a fresh directory for each test.

    args:
        tmp_path: Isolated test directory.
        project_root: Repository root containing processing defaults.

    returns:
        Directory containing editable processing YAML files.
    """
    shutil.copytree(project_root / "configs/dataset/processing", tmp_path, dirs_exist_ok=True)
    return tmp_path


@pytest.fixture
def judgment_payload():
    """
    Create a structurally valid judgment for isolated validation checks.

    args:
        None

    returns:
        Synthetic SAOS judgment payload.
    """
    return {
        "data": {
            "id": 254930,
            "judgmentDate": "2020-05-12",
            "courtType": "COMMON",
            "judgmentType": "SENTENCE",
            "courtCases": [{"caseNumber": "I C 42/20"}],
            "division": {
                "id": 10,
                "name": "I Wydział Cywilny",
                "court": {
                    "id": 1,
                    "name": "Sąd Okręgowy w Warszawie",
                    "type": "REGIONAL",
                },
            },
            "textContent": "<p>Zasądza 10 000 zł tytułem zadośćuczynienia.</p>",
        }
    }


@pytest.fixture(
    params=sorted((PROJECT_ROOT / "fixtures").glob("*/model_calls.json")),
    ids=lambda path: path.parent.name,
)
def model_calls_path(request):
    """Select a historical extraction replay, skipping when local inputs are absent.

    args:
        request: Pytest parametrized fixture request.

    returns:
        Historical model-call JSON path.
    """
    return request.param


@pytest.fixture
def locality_database(tmp_path):
    """Build a small GeoPackage-shaped database for SQL and snapshot checks.

    args:
        tmp_path: Isolated test directory.

    returns:
        Path to a valid locality database with one city and one village.
    """
    import sqlite3
    from contextlib import closing

    path = tmp_path / "localities ?#.gpkg"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "CREATE TABLE OT_ADMS_P (NAZWA, RODZAJ, LICZBAMIESZKANCOW, "
            "IDENTYFIKATORSIMC, IDENTYFIKATORTERC, IDENTYFIKATORPRNG, WERSJA)"
        )
        connection.executemany(
            "INSERT INTO OT_ADMS_P VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("Pisz", "miasto", 19000, "1", "2", "3", "2026"),
                ("Wieś", "wieś", 100, "4", "5", "6", "2026"),
            ],
        )
        connection.commit()
    return path
