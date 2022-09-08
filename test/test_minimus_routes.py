import unittest

from minimus import Minimus
from thread_killable import ThreadKillable

import requests

base_url = 'http://localhost:5000'
route1 = '/test'
route2 = '/test/extended'
message_1 = "Welcome Everyone"
message_2 = "The Cake is a Lie"
        
class TestMinimusRoutes(unittest.TestCase):
    def setUp(self):
        self.app = Minimus(__name__)
        
        # set up the routes
        self.app.add_route(route1, route1_view)
        self.app.add_route(route2, route2_view)
        
        self.new_thread = ThreadKillable(target=self.app.run)
        self.new_thread.start()
    
    def tearDown(self):
        self.new_thread.kill()
        self.new_thread.join()    
        
    def test_routes_1(self):
        r1 = requests.get(base_url + route1)
        self.assertEqual(200, r1.status_code)
        self.assertIn(message_1, r1.text)
        
    def test_route2(self):
        r2 = requests.get(base_url + route2)
        self.assertEqual(200, r2.status_code)
        self.assertIn(message_2, r2.text)
        
        
def route1_view(env):
    """a test route 1"""
    return message_1

def route2_view(env):
    """a test route 2"""
    return message_2

        
if __name__ == '__main__':
    unittest.main()