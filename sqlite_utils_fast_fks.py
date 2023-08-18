import click
from sqlite_utils import hookimpl

from typing import Iterable, Tuple, Dict, cast


@hookimpl
def register_commands(cli):
    @cli.command(name="fast-fks")
    @click.argument(
        "path",
        type=click.Path(exists=True, file_okay=True, dir_okay=False, allow_dash=False),
        required=True,
    )
    @click.argument("foreign_key", nargs=-1)
    def fast_fks(path, foreign_key):
        """
        Add multiple new foreign key constraints to a database

        Example:

        \b
            sqlite-utils fast-fks my.db \\
                books author_id authors id \\
                authors country_id countries id
        
        Documentation: https://github.com/simonw/sqlite-utils-fast-fks
        """
        from sqlite_utils.db import AlterError, Database

        db = Database(path)
        if len(foreign_key) % 4 != 0:
            raise click.ClickException(
                "Each foreign key requires four values: table, column, other_table, other_column"
            )
        tuples = []
        for i in range(len(foreign_key) // 4):
            tuples.append(tuple(foreign_key[i * 4 : (i * 4) + 4]))
        try:
            add_foreign_keys(db, tuples)
        except AlterError as e:
            raise click.ClickException(e)


def add_foreign_keys(db, foreign_keys: Iterable[Tuple[str, str, str, str]]):
    """
    :param foreign_keys: A list of  ``(table, column, other_table, other_column)``
        tuples
    """
    from sqlite_utils.db import AlterError, Table

    # foreign_keys is a list of explicit 4-tuples
    assert all(
        len(fk) == 4 and isinstance(fk, (list, tuple)) for fk in foreign_keys
    ), "foreign_keys must be a list of 4-tuples, (table, column, other_table, other_column)"

    foreign_keys_to_create = []

    # Verify that all tables and columns exist
    for table, column, other_table, other_column in foreign_keys:
        if not db[table].exists():
            raise AlterError("No such table: {}".format(table))
        table_obj = db[table]
        if not isinstance(table_obj, Table):
            raise AlterError("Must be a table, not a view: {}".format(table))
        table_obj = cast(Table, table_obj)
        if column not in table_obj.columns_dict:
            raise AlterError("No such column: {} in {}".format(column, table))
        if not db[other_table].exists():
            raise AlterError("No such other_table: {}".format(other_table))
        if other_column != "rowid" and other_column not in db[other_table].columns_dict:
            raise AlterError(
                "No such other_column: {} in {}".format(other_column, other_table)
            )
        # We will silently skip foreign keys that exist already
        if not any(
            fk
            for fk in table_obj.foreign_keys
            if fk.column == column
            and fk.other_table == other_table
            and fk.other_column == other_column
        ):
            foreign_keys_to_create.append((table, column, other_table, other_column))

    # Construct SQL for use with "UPDATE sqlite_master SET sql = ? WHERE name = ?"
    table_sql: Dict[str, str] = {}
    for table, column, other_table, other_column in foreign_keys_to_create:
        old_sql = table_sql.get(table, db[table].schema)
        extra_sql = ",\n   FOREIGN KEY([{column}]) REFERENCES [{other_table}]([{other_column}])\n".format(
            column=column, other_table=other_table, other_column=other_column
        )
        # Stick that bit in at the very end just before the closing ')'
        last_paren = old_sql.rindex(")")
        new_sql = old_sql[:last_paren].strip() + extra_sql + old_sql[last_paren:]
        table_sql[table] = new_sql

    # And execute it all within a single transaction
    with db.conn:
        cursor = db.conn.cursor()
        schema_version = cursor.execute("PRAGMA schema_version").fetchone()[0]
        cursor.execute("PRAGMA writable_schema = 1")
        for table_name, new_sql in table_sql.items():
            cursor.execute(
                "UPDATE sqlite_master SET sql = ? WHERE name = ?",
                (new_sql, table_name),
            )
        cursor.execute("PRAGMA schema_version = %d" % (schema_version + 1))
        cursor.execute("PRAGMA writable_schema = 0")
    # Have to VACUUM outside the transaction to ensure .foreign_keys property
    # can see the newly created foreign key.
    db.vacuum()
