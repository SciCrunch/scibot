import unittest
from flask import request
from scibot.bookmarklet import main as bookmarklet_main
from test.testing_data import form_data


def start_uri(uri):
    # nothing real is being done, so alway return not running
    return False


class TestRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = bookmarklet_main()
        cls.app.URL_LOCK.start_uri = start_uri
        print(list(cls.app.view_functions.keys()))

    def test_bookmarket(self):
        func = self.app.view_functions['bookmarklet']
        with self.app.test_request_context('/bookmarket'):
            hrm = func()

    def test_rrid_post(self):
        func = self.app.view_functions['rrid']
        with self.app.test_request_context('/rrid', method='POST'):
            request.form = form_data
            hrm = func()

    def test_rrid_options(self):
        func = self.app.view_functions['rrid']
        with self.app.test_request_context('/rrid', method='OPTIONS'):
            hrm = func()
