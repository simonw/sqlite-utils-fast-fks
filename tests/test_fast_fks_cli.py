from sqlite_utils import Database
from sqlite_utils.db import ForeignKey
from sqlite_utils.cli import cli
from click.testing import CliRunner
import pytest


@pytest.fixture
def db_and_db_path(tmpdir):
    db_path = str(tmpdir / "data.db")
    db = Database(db_path)
    db["country"].insert_all([{"id": 1, "name": "United Kingdom"}])
    db["continent"].insert_all([{"id": 1, "name": "Europe"}])
    db["places"].insert(
        {
            "id": 1,
            "name": "London",
            "country_id": 1,
            "continent_id": 1,
        }
    )
    return db, db_path


@pytest.mark.parametrize(
    "args,expected",
    (
        (
            ["places", "country_id", "country", "id"],
            [ForeignKey("places", "country_id", "country", "id")],
        ),
        (
            [
                "places",
                "country_id",
                "country",
                "id",
                "places",
                "continent_id",
                "continent",
                "id",
            ],
            [
                ForeignKey("places", "continent_id", "continent", "id"),
                ForeignKey("places", "country_id", "country", "id"),
            ],
        ),
    ),
)
def test_fast_fks(db_and_db_path, args, expected):
    db, db_path = db_and_db_path
    assert db["places"].foreign_keys == []
    runner = CliRunner()
    result = runner.invoke(cli, ["fast-fks", db_path] + args)
    assert result.exit_code == 0
    assert db["places"].foreign_keys == expected


@pytest.mark.parametrize(
    "args,expected_error",
    (
        (
            ["places", "country_id"],
            "Each foreign key requires four values: table, column, other_table, other_column",
        ),
        (
            ["places", "country_id", "country"],
            "Each foreign key requires four values: table, column, other_table, other_column",
        ),
        (
            ["places", "country_id", "country", "invalid"],
            "No such other_column: invalid in country",
        ),
    ),
)
def test_fast_fks_errors(db_and_db_path, args, expected_error):
    db, db_path = db_and_db_path
    assert db["places"].foreign_keys == []
    runner = CliRunner()
    result = runner.invoke(cli, ["fast-fks", db_path] + args)
    assert result.exit_code == 1
    assert expected_error in result.output
