import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--batch",
        action="store",
        metavar="BATCH",
        help="only run tests for the batch BATCH.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "batch(id): mark test to run only for given batch"
    )


def pytest_runtest_setup(item):
    batch_ids = [mark.args[0] for mark in item.iter_markers(name="batch")]
    if batch_ids:
        if item.config.getoption("--batch") not in batch_ids:
            pytest.skip("test requires batch in {!r}".format(batch_ids))
