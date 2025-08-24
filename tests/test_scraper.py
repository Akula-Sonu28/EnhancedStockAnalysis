import unittest
from src.nse_scraper import get_top_150_stock_data, fetch_stock_data

class TestScraper(unittest.TestCase):
    def test_get_top_150_stock_data(self):
        stock_data = get_top_150_stock_data()
        self.assertIsNotNone(stock_data)
        self.assertIsInstance(stock_data, list)
        self.assertTrue(len(stock_data) > 0)
        
    def test_fetch_stock_data(self):
        # Test with a known stock
        symbol = "RELIANCE"
        stock_info = fetch_stock_data(symbol)
        self.assertIsNotNone(stock_info)
        self.assertIsInstance(stock_info, dict)

if __name__ == '__main__':
    unittest.main()
