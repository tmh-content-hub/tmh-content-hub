"""Route integration tests with a temporary SQLite DB adapting PostgreSQL syntax.
Production PostgreSQL migration still needs a staging deployment smoke test.
"""
import sqlite3
import json
import sys
import unittest
from datetime import date, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, session, abort
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from website_offers import register, today_uk

sqlite3.register_converter('UPLOADS', lambda value: json.loads(value.decode()) if value else [])
sqlite3.register_adapter(date, lambda value: value.isoformat())
sqlite3.register_converter('DATE', lambda value: date.fromisoformat(value.decode()))

class Cursor:
    def __init__(self, db): self.raw = db.cursor()
    def __enter__(self): return self
    def __exit__(self, *args): self.raw.close()
    def execute(self, sql, params=()):
        if sql.startswith('ALTER TABLE website_offer_publications ADD COLUMN IF NOT EXISTS'):
            columns = [r[1] for r in self.raw.execute('PRAGMA table_info(website_offer_publications)').fetchall()]
            if 'gallery_image_urls' in columns:
                return self.raw.execute('SELECT 1')
            sql = sql.replace('ADD COLUMN IF NOT EXISTS', 'ADD COLUMN')
        sql = sql.replace('%s', '?').replace('TIMESTAMPTZ', 'TEXT').replace('NOW()', 'CURRENT_TIMESTAMP')
        return self.raw.execute(sql, params)
    def fetchone(self):
        row = self.raw.fetchone()
        return dict(row) if row else None
    def fetchall(self): return [dict(row) for row in self.raw.fetchall()]
class Connection:
    def __init__(self, db): self.db = db
    def cursor(self, **kwargs): return Cursor(self.db)
    def commit(self): self.db.commit()
    def close(self): pass

def authenticated(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'): abort(401)
        return fn(*args, **kwargs)
    return wrapped

class WebsiteOffersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)
        cls.db.row_factory = sqlite3.Row
        cls.db.execute('PRAGMA foreign_keys=ON')
        cls.db.executescript('''CREATE TABLE customers(id TEXT PRIMARY KEY);
            CREATE TABLE supplier_offers(id TEXT PRIMARY KEY, customer_id TEXT,
            caption TEXT, refined_caption TEXT, image_urls UPLOADS, submitted_at TEXT);''')
        cls.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1]/'templates'))
        cls.app.secret_key = 'tests-only'
        cls.app.testing = True
        cls.app.add_url_rule('/offers', 'offers', lambda: '')
        cls.app.add_url_rule('/', 'dashboard', lambda: '')
        register(cls.app, lambda: Connection(cls.db), authenticated)

    def setUp(self):
        self.db.executescript('DELETE FROM website_offer_publications; DELETE FROM website_offer_feeds; DELETE FROM supplier_offers; DELETE FROM customers;')
        self.db.executemany('INSERT INTO customers VALUES (?)', [('alice',), ('bob',)])
        self.db.executemany('INSERT INTO supplier_offers VALUES (?,?,?,?,?,?)', [
            ('offer-a','alice','Private supplier caption','Refined public candidate','','2026-01-01'),
            ('offer-b','bob','Other agent private caption','','','2026-01-02')])
        self.db.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess: sess['user_id'] = 'alice'
        response = self.client.get('/website-offers')
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess: self.csrf = sess['website_offers_csrf']
        self.slug = self.db.execute('SELECT slug FROM website_offer_feeds WHERE customer_id=?', ('alice',)).fetchone()['slug']

    def post(self, **overrides):
        data = dict(csrf=self.csrf, offer_id='offer-a', action='publish', title='Test holiday',
                    description='Confirmed public copy', price_text='£899pp',
                    price_conditions='Two sharing, June departures', expires_on=str(today_uk()+timedelta(days=2)), rights_confirmed='yes')
        data.update(overrides)
        return self.client.post('/website-offers', data=data)

    def feed(self, **kwargs): return self.client.get(f'/feed/offers/{self.slug}.json', **kwargs)

    def test_publish_feed_allowlist_and_revalidation(self):
        self.assertEqual(self.post().status_code, 302)
        response = self.feed()
        offer = response.json['offers'][0]
        self.assertEqual(offer['price_text'], 'from £899pp')
        self.assertEqual(set(offer), {'id','title','description','image_url','price_text','price_conditions','destination','board','duration','expires_on','supplier_name','gallery_image_urls'})
        self.assertNotIn('alice', response.get_data(as_text=True))
        self.assertNotIn('Private supplier', response.get_data(as_text=True))
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(self.feed(headers={'If-None-Match':response.headers['ETag']}).status_code,304)
        self.post(action='withdraw')
        self.assertEqual(self.feed(headers={'If-None-Match':response.headers['ETag']}).status_code,200)
        self.assertEqual(self.feed().json['offers'], [])

    def test_draft_expiry_and_all_months(self):
        self.post(action='draft')
        self.assertEqual(self.feed().json['offers'], [])
        self.post(expires_on=str(today_uk()))
        self.assertEqual(len(self.feed().json['offers']),1)
        self.db.execute('UPDATE website_offer_publications SET expires_on=?',(today_uk()-timedelta(days=1),))
        self.assertEqual(self.feed().json['offers'], [])
        self.assertIn('Expired',self.client.get('/website-offers').get_data(as_text=True))

    def test_ownership_csrf_auth(self):
        self.assertEqual(self.post(offer_id='offer-b').status_code,404)
        self.assertEqual(self.post(csrf='wrong').status_code,400)
        with self.client.session_transaction() as sess: sess.clear()
        self.assertEqual(self.client.get('/website-offers').status_code,401)
        self.assertEqual(self.post().status_code,401)
        self.assertEqual(self.feed().status_code,200)

    def test_invalid_publication_never_goes_live(self):
        for override in [dict(title=''), dict(rights_confirmed=''), dict(price_conditions=''),
                         dict(expires_on='bad'), dict(expires_on=str(today_uk()-timedelta(days=1))),
                         dict(image_url='https://other.example/stolen.jpg'), dict(title='x'*181)]:
            response = self.post(**override)
            self.assertEqual(response.status_code,200)
            self.assertIn('role="alert"',response.get_data(as_text=True))
            self.assertEqual(self.feed().json['offers'], [])

    def test_blank_price_text_only_snapshot_delete(self):
        self.post(price_text='',price_conditions='')
        offer = self.feed().json['offers'][0]
        self.assertEqual(offer['price_text'],'')
        self.assertEqual(offer['image_url'],'')
        self.db.execute("UPDATE supplier_offers SET refined_caption='New unreviewed copy' WHERE id='offer-a'")
        self.assertEqual(self.feed().json['offers'][0]['description'],'Confirmed public copy')
        self.db.execute("DELETE FROM supplier_offers WHERE id='offer-a'")
        self.assertEqual(self.feed().json['offers'],[])

    def test_image_validation_and_explicit_disable(self):
        from website_offers import normalise
        base = dict(action='draft',expires_on=str(today_uk()),image_url='https://storage.example/image.jpg')
        self.assertEqual(normalise(base,[base['image_url']])['image_url'],base['image_url'])
        self.assertEqual(normalise(dict(base,image_url=''),[base['image_url']])['image_url'],'')
        with self.assertRaises(ValueError): normalise(dict(base,image_url='javascript:alert(1)'),['javascript:alert(1)'])

    def test_unknown_slug_cors_and_options(self):
        response=self.client.get('/feed/offers/unknown.json')
        self.assertEqual(response.status_code,404)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'],'*')
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(self.client.options(f'/feed/offers/{self.slug}.json').status_code,204)

    def test_agents_have_separate_feeds(self):
        self.post()
        alice_slug = self.slug
        with self.client.session_transaction() as sess: sess['user_id'] = 'bob'
        self.client.get('/website-offers')
        with self.client.session_transaction() as sess: self.csrf = sess['website_offers_csrf']
        self.post(offer_id='offer-b', title='Bob public holiday')
        self.assertEqual([o['title'] for o in self.feed().json['offers']], ['Test holiday'])
        bob_slug = self.db.execute("SELECT slug FROM website_offer_feeds WHERE customer_id='bob'").fetchone()['slug']
        self.assertNotEqual(alice_slug,bob_slug)
        self.assertEqual([o['title'] for o in self.client.get(f'/feed/offers/{bob_slug}.json').json['offers']], ['Bob public holiday'])

    def test_feed_failure_is_generic_and_not_cached(self):
        from unittest.mock import patch
        with patch.object(Connection,'cursor',side_effect=RuntimeError('private database details')):
            with self.assertLogs(self.app.logger,level='ERROR'):
                response=self.feed()
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private database details',response.get_data(as_text=True))
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(response.headers['Access-Control-Allow-Origin'],'*')

    def test_gallery_publishing_selection_and_disable(self):
        images = ['https://storage.example/one.jpg', 'https://storage.example/two.jpg', 'https://storage.example/three.jpg']
        self.db.execute("UPDATE supplier_offers SET image_urls=? WHERE id='offer-a'", (json.dumps(images),))
        self.assertEqual(self.post(image_url=images[0], gallery_images=[images[1], images[0], images[1]]).status_code,302)
        self.assertEqual(self.feed().json['offers'][0]['gallery_image_urls'],images[:2])
        self.post(image_url=images[1],gallery_images=[])
        self.assertEqual(self.feed().json['offers'][0]['gallery_image_urls'],[images[1]])
        self.post(image_url='',gallery_images=images)
        self.assertEqual(self.feed().json['offers'][0]['gallery_image_urls'],[])
        self.assertEqual(self.feed().json['offers'][0]['image_url'],'')

    def test_gallery_rejects_foreign_photos_and_preserves_attempt(self):
        images = ['https://storage.example/one.jpg', 'https://storage.example/two.jpg']
        self.db.execute("UPDATE supplier_offers SET image_urls=? WHERE id='offer-a'", (json.dumps(images),))
        response = self.post(image_url=images[0],gallery_images=['https://other.example/foreign.jpg'])
        self.assertIn('Every gallery photo',response.get_data(as_text=True))
        self.assertEqual(self.feed().json['offers'],[])
        response = self.post(image_url=images[0],gallery_images=[images[1]],title='')
        self.assertIn('value="https://storage.example/two.jpg" checked',response.get_data(as_text=True))

    def test_escaped_editor(self):
        self.post(title='<script>alert(1)</script>')
        page=self.client.get('/website-offers').get_data(as_text=True)
        self.assertNotIn('<script>alert(1)</script>',page)
        self.assertIn('&lt;script&gt;',page)

if __name__ == '__main__': unittest.main()
