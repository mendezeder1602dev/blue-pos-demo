from pathlib import Path

from model.schema import create_database

from tests.util.general import TEST_REPORT_PATH


def __delete_test_database():
    db_file = Path('test.db')
    if db_file.exists():
        db_file.unlink()


def __create_generated_report_folder():
    if not TEST_REPORT_PATH.exists():
        TEST_REPORT_PATH.mkdir(parents=True)


def set_up():
    __create_generated_report_folder()
    __delete_test_database()

    create_database('sqlite:///test.db')


def tear_down():
    __delete_test_database()
