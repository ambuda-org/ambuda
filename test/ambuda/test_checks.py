from ambuda import checks


def test_check_database_engine(client, db_engine):
    checks._check_database_engine(db_engine)
