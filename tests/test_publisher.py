import unittest
import json
import os
import sys

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from publish_to_fb import (
    clean_html_text,
    get_posted_identifiers,
    is_already_posted,
    generate_facebook_post,
    SITES
)

class TestPublisher(unittest.TestCase):
    def test_clean_html_text(self):
        raw = "<p>This is a <b>great</b> coffee guide! Read more at...</p>"
        cleaned = clean_html_text(raw)
        self.assertIn("This is a great coffee guide!", cleaned)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("Read more", cleaned)

    def test_posted_identifiers(self):
        history = {
            "posted_articles": [
                {"guid": "https://example.com/?p=101", "url": "https://example.com/post-one/"}
            ],
            "last_post_date": {}
        }
        seen = get_posted_identifiers(history)
        self.assertIn("https://example.com/?p=101", seen)
        self.assertIn("https://example.com/post-one", seen)

    def test_is_already_posted(self):
        posted_set = {"guid-123", "https://example.com/art-1"}
        self.assertTrue(is_already_posted({"guid": "guid-123", "link": "https://example.com/art-2"}, posted_set))
        self.assertTrue(is_already_posted({"guid": "guid-999", "link": "https://example.com/art-1/"}, posted_set))
        self.assertFalse(is_already_posted({"guid": "guid-999", "link": "https://example.com/art-new/"}, posted_set))

    def test_generate_facebook_post(self):
        article = {
            "title": "Best Pour Over Technique",
            "link": "https://www.fullcoffeeroast.com/pour-over/",
            "description": "Learn the best pour over method. It makes your coffee taste smoother and brighter."
        }
        site_cfg = SITES[0]
        post = generate_facebook_post(site_cfg, article, is_backfill=True)
        self.assertIn("Best Pour Over Technique", post)
        self.assertIn("👉 Read the full article here:", post)
        self.assertIn(site_cfg["hashtags"], post)

if __name__ == "__main__":
    unittest.main()
