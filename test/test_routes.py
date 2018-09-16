import unittest
from flask import request
from scibot.bookmarklet import main as bookmarklet_main
from test.testing_data import form_data
from IPython import embed

def start_uri(uri):
    # nothing real is being done, so alway return not running
    return False

app = bookmarklet_main()
app.URL_LOCK.start_uri = start_uri
print(list(app.view_functions.keys()))
class TestRoutes(unittest.TestCase):
    def test_bookmarket(self):
        func = app.view_functions['bookmarklet']
        with app.test_request_context('/bookmarket'):
            hrm = func()

    def test_rrid_post(self):
        func = app.view_functions['rrid']
        with app.test_request_context('/rrid', method='POST'):
            request.form = form_data
            hrm = func()

    def test_rrid_options(self):
        func = app.view_functions['rrid']
        with app.test_request_context('/rrid', method='OPTIONS'):
            hrm = func()
