def pytest_configure(config):
    # pytest-bdd turns each Gherkin tag into a pytest mark.
    config.addinivalue_line('markers', 'checkout: the checkout feature')
