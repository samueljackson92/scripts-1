"""Run all unit tests
"""
import unittest

TEST_MODULES = ["ProfileTest", "FittingOptionsTest"]

test_loader = unittest.defaultTestLoader
suite = unittest.TestSuite()
for name in TEST_MODULES:
    suite.addTests(test_loader.loadTestsFromName("vesuvio.tests.{0}".format(name)))

unittest.TextTestRunner(verbosity=2).run(suite)