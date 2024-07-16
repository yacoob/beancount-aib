"""Register stringio and filecontents pytest markers."""


def pytest_configure(config):  # noqa: D103
    config.addinivalue_line(
        'markers',
        'stringio: input_file should return a io.StringIO instead of StringMemo',
    )
    config.addinivalue_line('markers', 'filecontents(str): input file for the importer')
