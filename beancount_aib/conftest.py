"""Register my pytest markers."""


def pytest_configure(config):  # noqa: D103
    config.addinivalue_line('markers', 'filecontents(str): input file for the importer')
