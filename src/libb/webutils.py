import base64
import contextlib
import cProfile
import datetime
import io
import json
import logging
import os
import posixpath
import pstats
import random
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from functools import update_wrapper, wraps
from itertools import accumulate
from urllib.parse import urlsplit, urlunsplit

from dateutil import parser

from libb import collapse, delay, expandabspath, grouper, splitcap

with contextlib.suppress(ImportError):
    import web

with contextlib.suppress(ImportError):
    import flask

logger = logging.getLogger(__name__)


# convenient placeholders for cookielib.Cookie
# allows us to quickly make Cookie(name='', value='', **COOKIE_DEFAULTS)
COOKIE_DEFAULTS = {
    'version': 0,
    'domain': '',
    'domain_specified': False,
    'domain_initial_dot': False,
    'port': None,
    'port_specified': False,
    'path': '/',
    'path_specified': True,
    'secure': False,
    'expires': None,
    'discard': True,
    'comment': None,
    'comment_url': None,
    'rest': {'HttpOnly': None},
    'rfc2109': False,
}


#
# django-like model/view mashups
#


def get_or_create(session, model, **kw):
    """A la django"""
    obj = session.query(model).filter_by(**kw).first()
    if not obj:
        obj = model(**kw)
        session.add(obj)
        session.flush()
    return obj


def paged(order_by_df, per_page_df):
    """Decorator to pass in default order / page / per page for pagination

    #. acquire the thread-local request object
    #. calculate pagination order by / offset / limit from request object
    #. patch the info into a database connection

    WARNING: careful not to patch MULTIPLE queries within the controller
    """

    def wrapper(query_fn):
        @wraps(query_fn)
        def paged_fn(*args, **kwargs):
            req = web.input()
            cn = web.ctx.cntc
            logger.warning(f'patching with req: {id(req)}')
            logger.warning(f'patching over cn: {id(cn)}')
            if 'f_' in req:
                logger.warning(f"Using filter f_={req.get('f_', '')}, NOT PAGED")
                return query_fn(*args, **kwargs)
            order_by = req.get('o_', order_by_df)
            order_by_dir = ' DESC ' if req.get('d_', 'a') == 'd' else ''
            page = int(req.get('p_', 0))
            per_page = int(req.get('n_', per_page_df))
            offset = page * per_page
            limit = per_page
            web.ctx.cntc.paged = (order_by + order_by_dir, offset, limit)
            ds = query_fn(*args, **kwargs)
            ds.page = page
            ds.per_page = per_page
            ds.total = web.ctx.cntc.paged_total
            return ds

        return paged_fn

    return wrapper

#
# webscraping utils
#


def rsleep(always=0, rand_extra=8):
    seconds = max(always + (random.randrange(0, max(rand_extra, 1) * 1000) * 0.001), 0)
    logger.debug(f'Sleeping {seconds:0.2f} seconds ...')
    delay(seconds)


def rand_retry(x_times=10, exception=Exception):
    """Randomly space out retries, to account for automated thresholding."""

    def wrapper(fn):
        @wraps(fn)
        def wrapped_fn(*args, **kwargs):
            logger.debug('Starting wrapped function')
            tries = 0
            while tries <= x_times:
                try:
                    return fn(*args, **kwargs)
                except exception as err:
                    logger.debug(err)
                    tries += 1
                    if tries > x_times:
                        logger.warning(f'Retried function {x_times} times without success.')
                        return
                    logger.warning(f'Retry number {tries}')
                    rsleep(tries)
        return wrapped_fn
    return wrapper

#
# commonly reused decorators
#


def cors_webpy(app, **kw):
    """Wrap a web.py controller with headers for cross origin resource sharing
    especially useful for views using resources from many websites
    see https://developer.mozilla.org/en-US/docs/Web/HTTP/Access_control_CORS
    for more information on CORS

    >>> app = web.application(('/mashup', 'mashup',), globals())

    >>> origins = ['mixpanel.com', 'mapbox.com']
    >>> methods = ['GET', 'HEAD', 'POST', 'PUT']
    >>> @cors_webpy(app, origin=origins, methods=methods, max_age=22)
    ... class mashup:
    ...     def GET(self):
    ...         return 'This page makes js calls to mixpanel and mapbox'

    >>> b = app.browser()
    >>> headers = b.open("/mashup").headers
    >>> 'mixpanel.com' in headers.get('Access-Control-Allow-Origin')
    True
    >>> 'mapbox.com' in headers.get('Access-Control-Allow-Origin')
    True
    >>> 'true' == headers.get('Access-Control-Allow-Credentials')
    True
    >>> 'POST' in headers.get('Access-Control-Allow-Methods')
    True
    >>> 'HEAD' in headers.get('Access-Control-Allow-Methods')
    True
    >>> '22' == headers.get('Access-Control-Max-Age')
    True
    """
    origin = kw.get('origin')
    credentials = kw.get('credentials', True)
    methods = kw.get('methods')
    headers = kw.get('headers')
    max_age = kw.get('max_age', 21600)
    attach_to_all = kw.get('attach_to_all', True)
    automatic_options = kw.get('automatic_options', True)

    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, datetime.timedelta):
        max_age = max_age.total_seconds()

    def allowed_methods(f):
        return [m for m in ['GET', 'HEAD', 'POST', 'PUT', 'DELETE'] if hasattr(f, m)]

    def get_methods(f):
        if methods is not None:
            return methods
        return allowed_methods(f)

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and web.ctx.method == 'OPTIONS':
                methods = allowed_methods(f)
                web.header('Allow', methods)
                return f(*args, **kwargs)
            if not attach_to_all and web.ctx.method != 'OPTIONS':
                return f(*args, **kwargs)

            h = web.header
            h('Access-Control-Allow-Origin', origin)
            h('Access-Control-Allow-Methods', get_methods(f))
            h('Access-Control-Allow-Credentials', str(credentials).lower())
            h('Access-Control-Max-Age', str(max_age))
            if headers is not None:
                h('Access-Control-Allow-Headers', headers)
            return f(*args, **kwargs)

        return update_wrapper(wrapped_function, f)

    return decorator


def cors_flask(app, **kw):
    """Wrap a flask controller with headers to allow cross origin resource sharing
    especially useful for views using resources from many websites

    >>> app = flask.Flask(__name__)

    >>> origins = ['mixpanel.com', 'mapbox.com']
    >>> methods = ['GET', 'HEAD', 'POST', 'PUT']
    >>> @app.route('/mashup')
    ... @cors_flask(app, origin=origins, methods=methods, max_age=22)
    ... def mashup():
    ...     return 'This page makes js calls to mixpanel and mapbox'

    we inject the allowed CORS domains ahead of time
    >>> client = app.test_client()
    >>> headers = client.get('/mashup').headers
    >>> 'mixpanel.com' in headers.get('Access-Control-Allow-Origin')
    True
    >>> 'mapbox.com' in headers.get('Access-Control-Allow-Origin')
    True
    >>> 'true' == headers.get('Access-Control-Allow-Credentials')
    True
    >>> 'POST' in headers.get('Access-Control-Allow-Methods')
    True
    >>> 'HEAD' in headers.get('Access-Control-Allow-Methods')
    True
    >>> '22' == headers.get('Access-Control-Max-Age')
    True
    """
    origin = kw.get('origin')
    credentials = kw.get('credentials', True)
    methods = kw.get('methods')
    headers = kw.get('headers')
    max_age = kw.get('max_age', 21600)
    attach_to_all = kw.get('attach_to_all', True)
    automatic_options = kw.get('automatic_options', True)

    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, datetime.timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and flask.request.method == 'OPTIONS':
                resp = app.make_default_options_response()
            else:
                resp = flask.make_response(f(*args, **kwargs))
            if not attach_to_all and flask.request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Allow-Credentials'] = str(credentials).lower()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)

    return decorator


def authd(checker_fn, fallback_fn):
    """Simple decorator that checks if a user meets an auth criterion

    === a web.py example

    >>> from http.cookiejar import Cookie
    >>> import web

    >>> urls = ('/another', 'another', '/(.*)', 'echo',)
    >>> app = web.application(urls, globals())

    >>> def forbid():
    ...     raise web.forbidden()

    >>> @authd(lambda: web.cookies().get('allowed'), forbid)
    ... class echo:
    ...     def GET(self, name):
    ...         return name

    >>> class another:
    ...     def GET(self):
    ...         return 'get'
    ...     @authd(lambda: web.cookies().get('allowed'), forbid)
    ...     def POST(self):
    ...         return 'post'

    >>> b = app.browser()
    >>> allowed = Cookie(name='allowed', value='1', **COOKIE_DEFAULTS)

    without the cookie, we cannot get to any controllers
    >>> b.open('/test').read()
    b'forbidden'

    once we add the cookie, we can
    >>> b.cookiejar.set_cookie(allowed)
    >>> b.open('/test').read()
    b'test'
    >>> b.reset()

    we can also restrict only certain methods
    >>> b.open('/another').read()
    b'get'
    >>> b.open('/another', data={'x':1}).read()
    b'forbidden'
    >>> b.cookiejar.set_cookie(allowed)
    >>> b.open('/another', data={'x':1}).read()
    b'post'

    === a flask example

    >>> app = flask.Flask(__name__)

    >>> @app.route('/restricted')
    ... @authd(lambda: flask.request.cookies.get('allowed'), lambda: flask.abort(403))
    ... def restricted_page():
    ...     return 'seekret!!!'

    can only access restricted controller when cookie 'allowed' is set
    >>> client = app.test_client()
    >>> '403 Forbidden' in str(client.get('/restricted').data)
    True
    >>> client.set_cookie('allowed', '1')
    >>> client.get('/restricted').data
    b'seekret!!!'
    """

    def wrapper(f):
        def authd_fn(*args, **kwargs):
            if not checker_fn():
                return fallback_fn()
            return f(*args, **kwargs)

        return update_wrapper(authd_fn, f)

    return wrapper


#
# cross site request forgery
#


def xsrf_token():
    """x-site request forgery protection token
    TODO add the xsrf tokens to forms
    """
    if 'xsrf' not in web.ctx.session:
        web.ctx.session.xsrf = uuid.uuid4().hex  # better use sha?
    return web.ctx.session.xsrf


def xsrf_protected(fn):
    """Decorator protecting PUT/POST requests from session riding
    TODO decorate controllers for xsrf prot forms
    """

    def dec_fn(*args, **kwargs):
        req = web.input()
        if not ('xsrf' in req and req.xsrf == web.ctx.session.pop('xsrf', None)):
            raise web.badrequest
        return fn(*args, **kwargs)

    return dec_fn


#
# decorators on REST api
#
VALID_KEY = re.compile('[a-zA-Z0-9_-]{1,255}')


def valid_api_key(key):
    """Check if key is suitable hash, if matches a validated user"""
    if VALID_KEY.match(key) is not None:
        return User.get_active_key(key)
    return False


def requires_api_key(fn):
    """Controller decorator defining how to allow api access
    (protects against directory traversal attacks / rolling perm's)
    """

    def decorated_fn(*args, **kwargs):
        if 'key' not in kwargs or not valid_api_key(kwargs['key']):
            web.badrequest()
        return fn(*args, **kwargs)

    return decorated_fn


#
# other rando website utility methods
#


def make_url(path, **params):
    """Consistent url generation
    - pass in arbitrary params inspired by `werkzeug.urls.Href`
    - always assume traditional multiple params (do not overwrite)
    - to overwrite, use special method `__replace__`
    - to ignore certain params, use `__ignore__` (handy for ajax back and forth)

    >>> ignore_fn = lambda x: x.startswith('_')
    >>> kw = dict(fuz=1, biz="boo")
    >>> make_url('/foo/', _format='excel', __ignore__=ignore_fn, **kw)
    '/foo/?fuz=1&biz=boo'
    >>> make_url('/foo/?bar=1', _format='excel', **kw)
    '/foo/?_format=excel&fuz=1&biz=boo&bar=1'
    >>> make_url('/foo/', bar=1, baz=2)
    '/foo/?bar=1&baz=2'
    >>> make_url('/foo/', **{'bar':1, 'fuz':(1,2,), 'biz':"boo"})
    '/foo/?bar=1&fuz=1&fuz=2&biz=boo'
    >>> make_url('/foo/?a=1&a=2')
    '/foo/?a=1&a=2'

    >>> kwargs = dict(fuz=1, biz="boo", __ignore__=ignore_fn)
    >>> xx = make_url('www.foobar.com/foo/', **kwargs)
    >>> 'www' in xx and 'foobar' in xx and '/foo/' in xx and 'fuz=1' in xx and 'biz=boo' in xx
    True
    >>> xx = make_url('/foo/', _format='excel', **kwargs)
    >>> '_format=excel' in xx
    False
    >>> 'fuz=1' in xx
    True
    >>> 'biz=boo' in xx
    True
    >>> yy = make_url('/foo/?bar=1', _format='excel', **kwargs)
    >>> 'bar=1' in yy
    True
    >>> '_format=excel' in yy
    False
    >>> zz = make_url('/foo/', **{'bar':1, 'fuz':(1,2,), 'biz':"boo"})
    >>> 'fuz=1' in zz
    True
    >>> 'fuz=2' in zz
    True
    >>> qq = make_url('/foo/?a=1&a=2')
    >>> 'a=1' in qq
    True
    >>> 'a=2' in qq
    True
    """
    replace = params.pop('__replace__', {})
    ignore = params.pop('__ignore__', None)

    params = {k: v() if callable(v) else v for k, v in params.items() if not k.startswith('__')}

    parsed = list(urllib.parse.urlparse(path))
    query = urllib.parse.parse_qsl(parsed[4])

    for k, v in query:
        if k in params:
            this = params[k]
            if hasattr(this, 'append'):
                this.append(v)
            else:
                this = [this] + [v]
            params[k] = this
        else:
            params[k] = v

    params.update(replace)

    if ignore:
        params = {k: v for k, v in params.items() if not ignore(k)}

    parsed[4] = urllib.parse.urlencode(params, doseq=True)
    cleanpath = urllib.parse.urlunparse(parsed)
    return cleanpath


def prefix_urls(pathpfx, classpfx, urls):
    newurls = []
    for i in range(0, len(urls), 2):
        newurls.extend((pathpfx + urls[i], classpfx + urls[i + 1]))
    return tuple(newurls)


def url_path_join(*parts):
    """Normalize url parts and join them with a slash.
    """
    schemes, netlocs, paths, queries, fragments = zip(*(urlsplit(part) for part in parts))
    scheme, netloc, query, fragment = first_of_each(schemes, netlocs, queries, fragments)
    path = '/'.join(x.strip('/') for x in paths if x)
    return urlunsplit((scheme, netloc, path, query, fragment))


def first_of_each(*sequences):
    return (next((x for x in sequence if x), '') for sequence in sequences)


_os_alt_seps: list[str] = [
    sep for sep in [os.sep, os.path.altsep] if sep is not None and sep != '/'
]


def safe_join(directory: str, *pathnames: str) -> str | None:
    """Safely join zero or more untrusted path components to a base
    directory to avoid escaping the base directory.
    via github.com/mitsuhiko/werkzeug security.py

    :param directory: The trusted base directory.
    :param pathnames: The untrusted path components relative to the
        base directory.
    :return: A safe path, otherwise ``None``.
    """
    if not directory:
        # Ensure we end up with ./path if directory="" is given,
        # otherwise the first untrusted part could become trusted.
        directory = '.'
    parts = [directory]
    for filename in pathnames:
        if filename != '':
            # normpath does not build path to root
            filename = posixpath.normpath(filename)
        if (any(sep in filename for sep in _os_alt_seps)
                or os.path.isabs(filename)
                or filename == '..'
                or filename.startswith('../')):
            return None
        parts.append(filename)
    return posixpath.join(*parts)


def local_or_static_join(static, somepath):
    """Infer if user is referring to template in their working directory, or in static"""
    localpath = expandabspath(somepath)
    staticpath = safe_join(static, somepath)
    if os.path.exists(localpath):
        return localpath
    if os.path.exists(staticpath):
        return staticpath
    raise OSError('That template does not exist on your path or in the local package.')


def inject_file(x):
    """Little wrapper for injecting css, js, etc, for html email templates"""
    with open(x, 'r', encoding='locale') as f:
        return f.read()


def inject_image(x):
    """base64 encoded code to put in src of an image tag in html"""
    _, ext = os.path.splitext(x)
    with open(x, 'rb') as f:
        code = base64.b64encode(f.read())
        return f"data:image/{ext.strip('.')};base64,{code}"


def build_breadcrumb(ctx):
    """Introspect web.py app_stack to build a reasonable breadcrumb"""
    paths = [x.fvars.get('breadcrumb', '') for x in web.ctx.app_stack]
    names = [' '.join(_.title() for _ in path.strip('/').split('_')) for path in paths]
    paths[0], names[0] = ctx.realhome, 'Home'
    paths = accumulate(paths)
    pathsnames = list(zip(paths, names))
    links = ['<a href="%s/">%s</a>' % _ for _ in pathsnames]
    to_render = ' >> '.join(links)
    return to_render


def breadcrumbify(url_app_tuple):
    """Assuming web.py style mapping, patch url mapping into subapps"""
    url_app_tuple = list(collapse(url_app_tuple))
    for i, app_or_url in enumerate(url_app_tuple):
        if isinstance(app_or_url, web.application):
            app_or_url.fvars['breadcrumb'] = url_app_tuple[i - 1]
    return url_app_tuple


def _format_link(cls):
    """For subapps (`web.application` instances within `urls` mapping)
    return the __name__ of the parent module, contained in the `fvars` attr
    """
    if isinstance(cls, web.application):
        return splitcap(cls.fvars['__name__'])
    return splitcap(str(cls))


def appmenu(urls, home='', fmt=_format_link):
    """Given a web.py (name,link,) tuple, home path (`web.ctx.homepath`), formatter
    builds a simple html menu to represent links in a web.py app

    >>> urls = (
    ...     'link/to/this/', 'this_thing',
    ...     'another/', 'another',
    ...     )
    >>> print((appmenu(urls, '/subapp/', splitcap)))
    <ul class="menu">
        <li><a href="/subapp/link/to/this/">This Thing</a></li>
        <li><a href="/subapp/another/">Another</a></li>
    </ul>
    >>> urls = (
    ...     '', 'index',
    ...     'sec/', 'sec',
    ...     'cftc/', 'cftc',
    ...     )
    >>> print((appmenu(urls[2:], 'http://localhost:8081/ops/regulatory/', lambda x: x.upper())))
    <ul class="menu">
        <li><a href="http://localhost:8081/ops/regulatory/sec/">SEC</a></li>
        <li><a href="http://localhost:8081/ops/regulatory/cftc/">CFTC</a></li>
    </ul>
    """
    links = (
        f"    <li><a href=\"{urllib.parse.urljoin(home, link.strip('/') + '/')}\">{fmt(name)}</a></li>\n"
        for link, name in grouper(collapse(urls), 2)
    )
    return f"<ul class=\"menu\">\n{''.join(links)}</ul>"


def scale(color, pct):
    def clamp(l, x, h):
        return min(max(l, x), h)

    if len(color) == 4:
        r, g, b = color[1], color[2], color[3]
        r = r + r
        g = g + g
        b = b + b
    else:
        r, g, b = color[1:3], color[3:5], color[5:]
    r = int(r, 16)
    g = int(g, 16)
    b = int(b, 16)
    r = clamp(0, int(r * pct + 0.5), 255)
    g = clamp(0, int(g * pct + 0.5), 255)
    b = clamp(0, int(b * pct + 0.5), 255)
    return f'#{r:X}{g:X}{b:X}'


def render_field(field):
    """Render either web.py or Django form"""

    def get_error(field):
        if hasattr(field, 'note'):
            return field.note
        if hasattr(field, 'errors'):
            return ', '.join(field.errors)
        return None

    def to_html(field):
        if isinstance(field, web.form.Input):
            return field.render()
        return str(field)

    html = []
    error = get_error(field)
    if error:
        html.append(f'<span class="flderr" title="{error}">')
    html.append(to_html(field))
    if error:
        html.append('</span>')
    return '\n'.join(html)


#
# these are not used yet ...
#


def get_or_create(session, model, **kw):
    """A la django"""
    obj = session.query(model).filter_by(**kw).first()
    if not obj:
        obj = model(**kw)
        session.add(obj)
        session.flush()
    return obj


def login_protected(priv_level=3, login_level=1):
    """Decorator protects session auth/auth, default priv=3"""

    def dec_fn(fn):
        def wrapped(*args, **kwargs):
            if web.ctx.session['login'] != login_level:
                msg = 'You are not logged in'
                web.ctx.session['msgs'].append((msg, 'error'))
                raise web.forbidden  # web.webapi.forbidden()
            if not web.ctx.session['priv'] >= priv_level:
                msg = 'Your permissions are not high enough'
                web.ctx.session['msgs'].append((msg, 'error'))
                raise web.forbidden
            return fn(*args, **kwargs)

        return wrapped

    return dec_fn


def userid_or_admin(fn):
    """Decorator limits access to your userid unless admin"""

    def dec_fn(*args, **kwargs):
        user_id = args[1]  # userid first REST arg for user manip
        if web.ctx.session['priv'] == 3 or int(user_id) == web.ctx.session['id']:
            return fn(*args, **kwargs)
        raise web.forbidden

    return dec_fn


def manager_or_admin(fn):
    """Decorator limits access to cancers user manages unless admin"""

    def dec_fn(*args, **kwargs):
        disease_id = args[1]  # diseaseid first REST arg for dis manip
        if web.ctx.session['priv'] == 3 or int(disease_id) == web.ctx.session['manages']:
            return fn(*args, **kwargs)
        raise web.forbidden

    return dec_fn


class JSONEncoderISODate(json.JSONEncoder):
    """json encoder adding assumption of ISO Date format

    >>> JSONEncoderISODate().encode({'dt': datetime.date(2014, 10, 2)})
    '{"dt": "2014-10-02"}'
    """

    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


class JSONDecoderISODate(json.JSONDecoder):
    """Json decoder parsing arbitrary date formats

    >>> JSONDecoderISODate().decode('{"dt": "2014-10-02"}')
    {'dt': datetime.datetime(2014, 10, 2, 0, 0)}
    """

    def __init__(self, **kw):
        super().__init__(object_hook=self._parse_date_hook, **kw)

    def _parse_date_hook(self, obj):
        if isinstance(obj, dict):
            for key in obj:
                if isinstance(obj[key], str):
                    with contextlib.suppress(ValueError, TypeError):
                        obj[key] = parser.parse(obj[key])

        return obj


class ProfileMiddleware:
    """Generic wsgi middleware for profiling wsgi calls
    WARNING: should always be last middleware loaded:
      #. you want profile everything else
      #. for speed, we return the result NOT the wrapped func

    >>> import logging
    >>> from io import StringIO
    >>> mock = StringIO()
    >>> sh = logging.StreamHandler(mock)
    >>> log = logging.getLogger('ProfilerTest')
    >>> log.setLevel(logging.DEBUG)
    >>> log.addHandler(sh)

    >>> import web
    >>> from webtest import TestApp

    >>> web.config.debug = False
    >>> urls = ('/', 'index',)
    >>> app = web.application(urls, globals())
    >>> profiled_app = ProfileMiddleware(app.wsgifunc(), log=log)

    >>> class index:
    ...     def GET(self):
    ...         return "Hello, world."

    >>> t = TestApp(profiled_app)
    >>> 'Hello' in t.get('/')
    True
    >>> sh.flush()
    >>> would_log = mock.getvalue()
    >>> print(would_log)
    Run finished in ... seconds
        ...
    <BLANKLINE>
    >>> 'Ordered by: internal time' in would_log
    True
    >>> 'due to restriction <20>' in would_log
    True
    >>> mock.close()

    >>> mock_cum = StringIO()
    >>> log.handlers[0].stream = mock_cum  # patch a clean buffer
    >>> by_cum = ProfileMiddleware(app.wsgifunc(), log=log, sort='name', count=30)
    >>> t_cum = TestApp(by_cum)
    >>> 'Hello' in t_cum.get("/")
    True
    >>> sh.flush()
    >>> would_log_cum = mock_cum.getvalue()
    >>> 'Ordered by: function name' in would_log_cum
    True
    >>> 'due to restriction <30>' in would_log_cum
    True
    >>> mock_cum.close()
    """

    def __init__(self, func, log=None, sort='time', count=20):
        self.func = func
        self.log = log
        self.sort = sort
        self.count = count

    def __call__(self, env, resp):
        stime = time.time()
        pr = cProfile.Profile()
        pr.enable()
        result = pr.runcall(self.func, env, resp)
        pr.disable()
        etime = time.time() - stime
        self.log.info(f'Run finished in {etime} seconds')

        with io.StringIO() as s:
            ps = pstats.Stats(pr, stream=s).sort_stats(self.sort)
            ps.print_stats(self.count)
            self.log.debug(s.getvalue())

        return result


def logerror(olderror, logger):
    """Wrap internalerror function to log the traceback too

    >>> import web
    >>> web.config.debug = False
    >>> urls = ('/', 'index',)

    >>> import logging
    >>> from io import StringIO
    >>> logger = logging.getLogger('LogTest')
    >>> stderr = sys.stderr
    >>> sys.stderr = mock = StringIO()
    >>> sh = logging.StreamHandler()
    >>> sh.setLevel(logging.ERROR)
    >>> logger.addHandler(sh)

    >>> app = web.application(urls, globals())
    >>> app.internalerror = logerror(app.internalerror, logger)

    >>> class index:
    ...     def GET(self):
    ...         return None+1

    >>> b = app.browser()
    >>> 'internal server error' in str(b.open('/').read())
    True
    >>> sys.stderr = stderr
    >>> 'TypeError' in str(mock.getvalue())
    True
    """

    def logerror_fn():
        theerr = olderror()
        _, exc, _ = sys.exc_info()
        logger.exception(exc)
        return theerr

    return logerror_fn


def validip6addr(address):
    """Returns True if `address` is a valid IPv6 address.

    >>> validip6addr('::')
    True
    >>> validip6addr('aaaa:bbbb:cccc:dddd::1')
    True
    >>> validip6addr('1:2:3:4:5:6:7:8:9:10')
    False
    >>> validip6addr('12:10')
    False
    """
    try:
        socket.inet_pton(socket.AF_INET6, address)
    except (socket.error, AttributeError, ValueError):
        return False

    return True


def validipaddr(address):
    """Returns True if `address` is a valid IPv4 address.

    >>> validipaddr('192.168.1.1')
    True
    >>> validipaddr('192.168. 1.1')
    False
    >>> validipaddr('192.168.1.800')
    False
    >>> validipaddr('192.168.1')
    False
    """
    try:
        octets = address.split('.')
        if len(octets) != 4:
            return False

        for x in octets:
            if ' ' in x:
                return False

            if not (0 <= int(x) <= 255):
                return False
    except ValueError:
        return False
    return True


def validipport(port):
    """Returns True if `port` is a valid IPv4 port.

    >>> validipport('9000')
    True
    >>> validipport('foo')
    False
    >>> validipport('1000000')
    False
    """
    try:
        if not (0 <= int(port) <= 65535):
            return False
    except ValueError:
        return False
    return True


def validip(ip, defaultaddr='0.0.0.0', defaultport=8080):
    """Returns `(ip_address, port)` from string `ip_addr_port`

    >>> validip('1.2.3.4')
    ('1.2.3.4', 8080)
    >>> validip('80')
    ('0.0.0.0', 80)
    >>> validip('192.168.0.1:85')
    ('192.168.0.1', 85)
    >>> validip('::')
    ('::', 8080)
    >>> validip('[::]:88')
    ('::', 88)
    >>> validip('[::1]:80')
    ('::1', 80)

    """
    addr = defaultaddr
    port = defaultport

    # Matt Boswell's code to check for ipv6 first
    match = re.search(r'^\[([^]]+)\](?::(\d+))?$', ip)  # check for [ipv6]:port
    if match:
        if validip6addr(match.group(1)):
            if match.group(2):
                if validipport(match.group(2)):
                    return (match.group(1), int(match.group(2)))
            else:
                return (match.group(1), port)
    elif validip6addr(ip):
        return (ip, port)
    # end ipv6 code

    ip = ip.split(':', 1)
    if len(ip) == 1:
        if not ip[0]:
            pass
        elif validipaddr(ip[0]):
            addr = ip[0]
        elif validipport(ip[0]):
            port = int(ip[0])
        else:
            raise ValueError(':'.join(ip) + ' is not a valid IP address/port')
    elif len(ip) == 2:
        addr, port = ip
        if not validipaddr(addr) or not validipport(port):
            raise ValueError(':'.join(ip) + ' is not a valid IP address/port')
        port = int(port)
    else:
        raise ValueError(':'.join(ip) + ' is not a valid IP address/port')
    return (addr, port)


def validaddr(string_):
    """Returns either (ip_address, port) or "/path/to/socket" from string_

    >>> validaddr('/path/to/socket')
    '/path/to/socket'
    >>> validaddr('8000')
    ('0.0.0.0', 8000)
    >>> validaddr('127.0.0.1')
    ('127.0.0.1', 8080)
    >>> validaddr('127.0.0.1:8000')
    ('127.0.0.1', 8000)
    >>> validip('[::1]:80')
    ('::1', 80)
    >>> validaddr('fff')
    Traceback (most recent call last):
        ...
    ValueError: fff is not a valid IP address/port
    """
    if '/' in string_:
        return string_
    return validip(string_)


def urlquote(val):
    """Quotes a string for use in a URL.

    >>> urlquote('://?f=1&j=1')
    '%3A//%3Ff%3D1%26j%3D1'
    >>> urlquote(None)
    ''
    >>> urlquote(u'\u203d')
    '%E2%80%BD'
    """
    if val is None:
        return ''

    val = str(val).encode('utf-8')
    return urllib.parse.quote(val)


def httpdate(date_obj):
    """Formats a datetime object for use in HTTP headers.

    >>> import datetime
    >>> httpdate(datetime.datetime(1970, 1, 1, 1, 1, 1))
    'Thu, 01 Jan 1970 01:01:01 GMT'
    """
    return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')


def parsehttpdate(string_):
    """Parses an HTTP date into a datetime object.

    >>> parsehttpdate('Thu, 01 Jan 1970 01:01:01 GMT')
    datetime.datetime(1970, 1, 1, 1, 1, 1)
    """
    try:
        t = time.strptime(string_, '%a, %d %b %Y %H:%M:%S %Z')
    except ValueError:
        return None
    return datetime.datetime(*t[:6])


def htmlquote(text):
    r"""Encodes `text` for raw use in HTML.

    >>> htmlquote(u"<'&\">")
    '&lt;&#39;&amp;&quot;&gt;'
    """
    text = text.replace('&', '&amp;')  # Must be done first!
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace("'", '&#39;')
    text = text.replace('"', '&quot;')
    return text


def htmlunquote(text):
    r"""Decodes `text` that's HTML quoted.

    >>> htmlunquote(u'&lt;&#39;&amp;&quot;&gt;')
    '<\'&">'
    """
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&gt;', '>')
    text = text.replace('&lt;', '<')
    text = text.replace('&amp;', '&')  # Must be done last!
    return text


def websafe(val):
    r"""Converts `val` so that it is safe for use in Unicode HTML.

    >>> websafe("<'&\">")
    '&lt;&#39;&amp;&quot;&gt;'
    >>> websafe(None)
    ''
    >>> websafe(u'\u203d') == u'\u203d'
    True
    """
    if val is None:
        return ''

    if isinstance(val, bytes):
        val = val.decode('utf-8')
    elif not isinstance(val, str):
        val = str(val)

    return htmlquote(val)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
