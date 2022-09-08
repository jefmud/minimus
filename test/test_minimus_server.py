import unittest

from minimus import Minimus
from thread_killable import ThreadKillable

import requests

base_url = 'http://localhost:5000'

class TestMinimus(unittest.TestCase):
    def setUp(self):
        self.app = Minimus(__name__)
        self.new_thread = ThreadKillable(target=self.app.run)
        self.new_thread.start()
    
    def tearDown(self):
        self.new_thread.kill()
        self.new_thread.join()
        
    def test_wsgiref_5000(self):
        print("test Minimus port 5000 default")
        r = requests.get(base_url)
        self.assertEqual(200,r.status_code)
        self.assertIn(self.app.logo(), r.text)
        
if __name__ == '__main__':
    unittest.main()