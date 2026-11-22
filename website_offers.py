"""Explicit, customer-owned publication snapshots for BTW websites."""
import hashlib
import json
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, date
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for
from psycopg2.extras import RealDictCursor

bp = Blueprint('website_offers', __name__)
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
FIELDS = {'title': 180, 'description': 6000, 'price_text': 120,
          'price_conditions': 2000, 'destination': 180, 'board': 180,
          'duration': 100, 'supplier_name': 180}


def today_uk():
    return datetime.now(ZoneInfo('Europe/London')).date()


def normalise(form, images):
    """Validate only supplied facts; never derive a price or protection claim."""
    data = {key: form.get(key, '').strip() for key in FIELDS}
    for key, maximum in FIELDS.items():
        if len(data[key]) > maximum:
            raise ValueError(f'{key.replace("_", " ").capitalize()} is too long (maximum {maximum} characters).')
    price = data['price_text']
    if price:
        data['price_text'] = 'from ' + re.sub(r'^from\s+', '', price, flags=re.I)
    try:
        data['expires_on'] = date.fromisoformat(form.get('expires_on', ''))
    except ValueError:
        raise ValueError('Choose an offer expiry date.')
    image = form.get('image_url', '').strip()
    if image and (image not in images or urlsplit(image).scheme != 'https'):
        raise ValueError('Choose an image uploaded with this offer, or select no image.')
    selected = form.getlist('gallery_images') if hasattr(form, 'getlist') else form.get('gallery_images', [])
    if not isinstance(selected, list):
        raise ValueError('Choose gallery photos from this offer’s uploads.')
    if any(not isinstance(url, str) or url not in images or urlsplit(url).scheme != 'https' for url in selected):
        raise ValueError('Every gallery photo must be an image uploaded with this offer.')
    # No image disables the whole gallery. The card image leads the gallery.
    gallery = list(dict.fromkeys([image] + selected)) if image else []
    data['gallery_image_urls'] = json.dumps(gallery)
    data['image_url'] = image
    data['published'] = form.get('action') == 'publish'
    if data['published']:
        if not data['title'] or not data['description']:
            raise ValueError('Add a headline and description before publishing.')
        if data['expires_on'] < today_uk():
            raise ValueError('An expired offer cannot be published. Check the supplier’s current details first.')
        if price and not data['price_conditions']:
            raise ValueError('Include the supplier’s price conditions and applicable dates.')
        if form.get('rights_confirmed') != 'yes':
            raise ValueError('Confirm permission to publish this copy and any selected image.')
    return data


def register(app, get_db, login_required):
    @contextmanager
    def database():
        conn = get_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield conn, cur
        finally:
            conn.close()

    def migrate():
        with database() as (conn, cur):
            cur.execute('''CREATE TABLE IF NOT EXISTS website_offer_feeds (
                customer_id TEXT PRIMARY KEY REFERENCES customers(id) ON DELETE CASCADE,
                slug TEXT UNIQUE NOT NULL)''')
            cur.execute('''CREATE TABLE IF NOT EXISTS website_offer_publications (
                offer_id TEXT PRIMARY KEY REFERENCES supplier_offers(id) ON DELETE CASCADE,
                public_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
                image_url TEXT NOT NULL DEFAULT '', price_text TEXT NOT NULL DEFAULT '',
                price_conditions TEXT NOT NULL DEFAULT '', destination TEXT NOT NULL DEFAULT '',
                board TEXT NOT NULL DEFAULT '', duration TEXT NOT NULL DEFAULT '',
                supplier_name TEXT NOT NULL DEFAULT '', expires_on DATE NOT NULL,
                published BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
            cur.execute("ALTER TABLE website_offer_publications ADD COLUMN IF NOT EXISTS gallery_image_urls TEXT NOT NULL DEFAULT '[]'")
            conn.commit()

    @bp.route('/website-offers', methods=['GET', 'POST'])
    @login_required
    def manage():
        customer_id = session['user_id']
        session.setdefault('website_offers_csrf', secrets.token_urlsafe(32))
        error = None
        attempted = None
        with database() as (conn, cur):
            if request.method == 'POST':
                if not secrets.compare_digest(request.form.get('csrf', ''), session['website_offers_csrf']):
                    abort(400, 'This form has expired. Reload the page and try again.')
                offer_id = request.form.get('offer_id', '')
                cur.execute('SELECT id, image_urls FROM supplier_offers WHERE id=%s AND customer_id=%s',
                            (offer_id, customer_id))
                owned = cur.fetchone()
                if not owned:
                    abort(404)
                action = request.form.get('action')
                if action == 'withdraw':
                    cur.execute('UPDATE website_offer_publications SET published=FALSE, updated_at=NOW() WHERE offer_id=%s', (offer_id,))
                    conn.commit()
                    return redirect(url_for('.manage', saved=1))
                if action not in ('draft', 'publish'):
                    abort(400)
                try:
                    data = normalise(request.form, owned['image_urls'] or [])
                    columns = list(data)
                    cur.execute('''INSERT INTO website_offer_publications
                        (offer_id, public_id, ''' + ','.join(columns) + ''') VALUES ('''
                        + ','.join(['%s'] * (len(columns) + 2)) + ''')
                        ON CONFLICT (offer_id) DO UPDATE SET '''
                        + ','.join(f'{k}=EXCLUDED.{k}' for k in columns) + ', updated_at=NOW()',
                        [offer_id, secrets.token_hex(12)] + [data[k] for k in columns])
                    conn.commit()
                    return redirect(url_for('.manage', saved=1))
                except ValueError as exc:
                    error = str(exc)
                    attempted = dict(request.form)
                    attempted['gallery_images'] = request.form.getlist('gallery_images')
            # Stable, non-identifying slug; no customer email/name/id in public feed.
            cur.execute('''INSERT INTO website_offer_feeds (customer_id, slug) VALUES (%s,%s)
                ON CONFLICT (customer_id) DO NOTHING''', (customer_id, 'agent-' + secrets.token_hex(12)))
            cur.execute('SELECT slug FROM website_offer_feeds WHERE customer_id=%s', (customer_id,))
            slug = cur.fetchone()['slug']
            cur.execute('''SELECT o.id, o.caption, o.refined_caption, o.image_urls,
                    p.offer_id AS saved_offer_id, p.title, p.description, p.image_url,
                    p.price_text, p.price_conditions, p.destination, p.board, p.duration,
                    p.supplier_name, p.expires_on, p.published, p.gallery_image_urls
                FROM supplier_offers o LEFT JOIN website_offer_publications p ON p.offer_id=o.id
                WHERE o.customer_id=%s ORDER BY o.submitted_at DESC''', (customer_id,))
            offers = [dict(row) for row in cur.fetchall()]
            conn.commit()
        for offer in offers:
            offer['gallery_images'] = json.loads(offer.get('gallery_image_urls') or '[]')
            offer['status'] = ('Expired' if offer['published'] and offer['expires_on'] < today_uk()
                               else 'Published' if offer['published'] else 'Draft')
            if not offer['saved_offer_id']:
                offer['gallery_images'] = offer.get('image_urls') or []
                offer['description'] = offer.get('refined_caption') or offer.get('caption') or ''
            if attempted and attempted['offer_id'] == offer['id']:
                for key in [*FIELDS, 'image_url', 'expires_on', 'gallery_images']:
                    offer[key] = attempted.get(key, '')
        response = app.make_response(render_template('website_offers.html', offers=offers,
            slug=slug, error=error, saved=request.args.get('saved'), fields=FIELDS,
            csrf=session['website_offers_csrf']))
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    @bp.route('/feed/offers/<slug>.json', methods=['GET', 'OPTIONS'])
    def feed(slug):
        if request.method == 'OPTIONS':
            response = app.make_response(('', 204))
        elif not SLUG.fullmatch(slug) or len(slug) > 80:
            response = jsonify(offers=[])
            response.status_code = 404
        else:
            try:
                with database() as (_, cur):
                    cur.execute('SELECT customer_id FROM website_offer_feeds WHERE slug=%s', (slug,))
                    owner = cur.fetchone()
                    if not owner:
                        response = jsonify(offers=[])
                        response.status_code = 404
                    else:
                        # Explicit public allowlist. Never SELECT * here.
                        cur.execute('''SELECT p.public_id AS id, p.title, p.description,
                            p.image_url, p.gallery_image_urls, p.price_text, p.price_conditions, p.destination,
                            p.board, p.duration, p.expires_on, p.supplier_name
                            FROM website_offer_publications p
                            JOIN supplier_offers o ON o.id=p.offer_id
                            WHERE o.customer_id=%s AND p.published=TRUE AND p.expires_on >= %s
                            ORDER BY p.updated_at DESC, p.public_id''', (owner['customer_id'], today_uk()))
                        rows = [dict(row) for row in cur.fetchall()]
                        for row in rows:
                            row['expires_on'] = row['expires_on'].isoformat()
                            row['gallery_image_urls'] = json.loads(row['gallery_image_urls'] or '[]') if row['image_url'] else []
                        response = jsonify(offers=rows)
                        # Revalidation prevents cached expired/withdrawn offers being served.
                        response.headers['Cache-Control'] = 'public, no-cache, must-revalidate'
                        response.set_etag(hashlib.sha256(response.get_data()).hexdigest())
                        response.make_conditional(request)
            except Exception:
                app.logger.exception('Public offers feed unavailable')
                response = jsonify(offers=[], error='Offers are temporarily unavailable.')
                response.status_code = 503
        if response.status_code not in (200, 304):
            response.headers['Cache-Control'] = 'no-store'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
        response.headers['Access-Control-Expose-Headers'] = 'ETag'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    app.register_blueprint(bp)
    try:
        migrate()
    except Exception:
        app.logger.exception('Website offers migration failed; check database access before launch')
