import unittest
from scibot.services import rrid_resolver_xml


class TestResolver(unittest.TestCase):
    def test_redirect(self):
        found_rrids = {}
        out = rrid_resolver_xml('%20rid_000041', found_rrids)

