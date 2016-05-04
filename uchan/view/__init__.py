import string
from urllib.parse import urlparse

import config
import random
from flask import send_from_directory, session, request, abort, url_for, render_template, jsonify
from functools import wraps
from markupsafe import escape, Markup
from sqlalchemy.orm.exc import NoResultFound
from uchan import g, app
from uchan.filter.app_filters import page_formatting
from uchan.lib.database import get_db
from uchan.lib.service import PageService


class ExtraJavascript:
    def __init__(self):
        self.js = ''

    def add(self, js):
        self.js += js

    def gather(self):
        return self.js


@app.context_processor
def inject_variables():
    site_config_cached = g.site_cache.find_site_config_cached()

    all_boards = None
    if site_config_cached.boards_top:
        all_boards = g.board_cache.all_boards()

    footer_pages_cached = g.page_cache.find_pages_for_type_cached(PageService.TYPE_FOOTER_PAGE)
    footer_pages = footer_pages_cached.pages if footer_pages_cached else []

    extra_javascript = ExtraJavascript()
    g.plugin_manager.execute_hook('extra_javascript', extra_javascript)

    header_links = [
        ('mod', url_for('mod.mod_auth')),
    ]

    return dict(all_boards=all_boards,
                header_links=header_links,
                site_config=site_config_cached,
                footer_pages=footer_pages,
                extra_javascript=extra_javascript)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = ''.join(
            random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(32))
    return session['_csrf_token']


def generate_csrf_token_html():
    return Markup('<input name="token" type="hidden" value="{}">'.format(escape(generate_csrf_token())))


def with_token():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not check_csrf_token(request.form.get('token')):
                abort(400)

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def check_csrf_token(form_token):
    session_token = session.get('_csrf_token', None)
    return session_token is not None and form_token is not None and session_token == form_token


def check_csrf_referer(request):
    referer = request.headers.get('Referer', None)
    if not referer:
        return False

    parsed_url = urlparse(referer)

    return '{}://{}'.format(parsed_url.scheme, parsed_url.hostname) == config.SITE_URL


def render_error(user_message, code=400, with_retry=False):
    if request.is_xhr:
        xhr_response = {
            'error': True
        }

        if user_message:
            xhr_response['message'] = page_formatting(user_message)

        return jsonify(xhr_response), code
    else:
        return render_template('error.html', message=user_message, with_retry=with_retry), code


app.jinja_env.globals['csrf_token'] = generate_csrf_token
app.jinja_env.globals['csrf_html'] = generate_csrf_token_html


def get_model_id(model, id):
    if type(id) != int or id <= 0 or id > 2 ** 32:
        abort(400)

    db = get_db()
    try:
        return db.query(model).filter_by(id=id).one()
    except NoResultFound:
        abort(404)


import uchan.view.index
import uchan.view.board
import uchan.view.post
import uchan.view.thread
import uchan.view.banned
import uchan.view.page
import uchan.view.verify
