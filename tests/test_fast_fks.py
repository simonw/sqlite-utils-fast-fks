from sqlite_utils import Database
from sqlite_utils.db import ForeignKey
from sqlite_utils_fast_fks import add_foreign_keys


def test_fast_fks():
    db = Database(memory=True)
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
    assert db["places"].foreign_keys == []
    add_foreign_keys(
        db,
        [
            ("places", "country_id", "country", "id"),
            ("places", "continent_id", "continent", "id"),
        ],
    )
    assert db["places"].foreign_keys == [
        ForeignKey("places", "continent_id", "continent", "id"),
        ForeignKey("places", "country_id", "country", "id"),
    ]
