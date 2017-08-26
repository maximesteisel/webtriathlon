import unittest
from unittest import TestCase
import os, sys, glob

import client

class DClientTest(TestCase):
    def setUp(self):
        self.dclient = client.DClient()
        self.connection = self.dclient.get_connection()

    def tearDown(self):
        for p in glob.glob("passages.*.save"):
            os.unlink(p)
        for p in glob.glob("wtencoder*.log"):
            os.unlink(p)

    def test_add_passage(self):
        status, id = self.dclient.add_passage(self.connection, station="P1", team=2,
                timestamp=1560)
        self.assertEqual(status, client.S_SAVED)
        self.assert_(id > -1)
        p = self.dclient.get_passage(self.connection, id)
        self.assertEqual(p["pk"], -1)
        self.assertEqual(p["fields"]["team"], 2)
        self.assertEqual(p["fields"]["station"], -1)

    def test_get_stage(self):
        status, id = self.dclient.add_passage(self.connection, station="P1",
                team=2, timestamp=1560)
        self.assertEqual(self.dclient.get_stage(self.connection, id), "")

    def test_add_passage_to_path(self):
        status, ids = self.dclient.add_passage_to_path(self.connection, station="P1",
                path="P", timestamp=1560)
        self.assertEqual(len(ids), 1)
        self.assert_(ids[0] > -1)
        self.assertEqual(status, client.S_SAVED)

    def test_modify_passage(self):
        status, (id,) = self.dclient.add_passage_to_path(self.connection, station="P1",
                category="P", timestamp=1560)
        status = self.dclient.modify_passage(self.connection, id, {})
        self.assertEqual(status, client.S_MODIFIED)

    def test_delete_passage(self):
        status, id = self.dclient.add_passage(self.connection, station="P1", team=2,
                timestamp=1560)
        status = self.dclient.delete_passage(self.connection, id)
        self.assertEqual(status, client.S_DELETED)
        self.assertRaises(KeyError, self.dclient.get_passage, self.connection, id)

        status, (id,) = self.dclient.add_passage_to_path(self.connection, station="P1",
                category="P", timestamp=1560)
        status = self.dclient.delete_passage(self.connection, id)
        self.assertEqual(status, client.S_DELETED)
        self.assertRaises(KeyError, self.dclient.get_passage, self.connection, id )

if __name__ == "__main__":
    unittest.main()
