from sqlalchemy import inspect, text

from database import engine


def column_exists(table_name: str, column_name: str) -> bool:
    inspector = inspect(engine)
    return column_name in [column["name"] for column in inspector.get_columns(table_name)]


def add_column_if_missing(table_name: str, column_name: str, sql: str):
    if column_exists(table_name, column_name):
        print(f"{table_name}.{column_name} already exists")
        return

    with engine.begin() as connection:
        connection.execute(text(sql))
    print(f"Added {table_name}.{column_name}")


def migrate():
    dialect = engine.dialect.name
    if dialect == "postgresql":
        sort_sql = "ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0"
        active_sql = "ALTER TABLE categories ADD COLUMN is_active BOOLEAN DEFAULT TRUE"
    else:
        sort_sql = "ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0"
        active_sql = "ALTER TABLE categories ADD COLUMN is_active BOOLEAN DEFAULT 1"

    add_column_if_missing("categories", "sort_order", sort_sql)
    add_column_if_missing("categories", "is_active", active_sql)

    with engine.begin() as connection:
        connection.execute(text("UPDATE categories SET sort_order = 0 WHERE sort_order IS NULL"))
        if dialect == "postgresql":
            connection.execute(text("UPDATE categories SET is_active = TRUE WHERE is_active IS NULL"))
        else:
            connection.execute(text("UPDATE categories SET is_active = 1 WHERE is_active IS NULL"))
    print("Category migration completed")


if __name__ == "__main__":
    migrate()
