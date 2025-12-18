from __future__ import annotations

import base64
import contextlib
import cProfile
import datetime
import io
import json
import logging
import os
import pathlib
import posixpath
import pstats
import random
import re
import socket
import sys
import time
import urllib.parse
import uuid
from functools import update_wrapper, wraps
from itertools import accumulate, starmap
from urllib.parse import urlsplit, urlunsplit

from dateutil import parser

from libb import collapse, expandabspath, grouper, splitcap

with contextlib.suppress(ImportError):
    import web

with contextlib.suppress(ImportError):
    import flask

logger = logging.getLogger(__name__)

__all__ = [
    'get_or_create',
    'paged',
    'rsleep',
    'rand_retry',
    'cors_webpy',
    'cors_flask',
    'authd',
    'xsrf_token',
    'xsrf_protected',
    'valid_api_key',
    'requires_api_key',
    'make_url',
    'prefix_urls',
    'url_path_join',
    'first_of_each',
    'safe_join',
    'local_or_static_join',
    'inject_file',
    'inject_image',
    'build_breadcrumb',
    'breadcrumbify',
    'appmenu',
    'scale',
    'render_field',
    'login_protected',
    'userid_or_admin',
    'manager_or_admin',
    'logerror',
    'validip6addr',
    'validipaddr',
    'validipport',
    'validip',
    'validaddr',
    'urlquote',
    'httpdate',
    'parsehttpdate',
    'htmlquote',
    'htmlunquote',
    'websafe',
    'JSONEncoderISODate',
    'JSONDecoderISODate',
    'ProfileMiddleware',
    'COOKIE_DEFAULTS',
]


class _CookieDefaults(dict):
    """Default kwargs for cookielib.Cookie constructor."""


COOKIE_DEFAULTS = _CookieDefaults({
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
})


#
# django-like model/view mashups
#


def get_or_create(session, model, **kw):
    """Get existing model instance or create new one (Django-style).

    :param session: SQLAlchemy session.
    :param model: SQLAlchemy model class.
    :param kw: Keyword arguments for filtering/creating.
    :returns: Existing or newly created model instance.
    """
    obj = session.query(model).filter_by(**kw).first()
    if not obj:
        obj = model(**kw)
        session.add(obj)
        session.flush()
    return obj


def paged(order_by_df, per_page_df):
    """Decorator to pass in default order/page/per page for pagination.

    Steps performed:

    1. Acquire the thread-local request object
    2. Calculate pagination order by/offset/limit from request object
    3. Patch the info into a database connection

    :param str order_by_df: Default column to order by.
    :param int per_page_df: Default number of items per page.
    :returns: Decorator function.

    .. warning::
        Careful not to patch MULTIPLE queries within the controller.
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
    """Sleep for a random amount of time.

    :param float always: Minimum seconds to sleep.
    :param float rand_extra: Maximum additional random seconds.
    """
    seconds = max(always + (random.randrange(0, max(rand_extra, 1) * 1000) * 0.001), 0)
    logger.debug(f'Sleeping {seconds:0.2f} seconds ...')
    time.sleep(seconds)


def rand_retry(x_times=10, exception=Exception):
    """Decorator that retries function with random delays.

    Useful for avoiding automated thresholding on web requests.

    :param int x_times: Maximum number of retries.
    :param exception: Exception type(s) to catch and retry on.
    :returns: Decorator function.
    """

    def wrapper(fn):
        @wraps(fn)
        def wrapped_fn(*args, **kwargs):
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
    """Wrap a web.py controller with CORS headers.

    Especially useful for views using resources from many websites.

    :param app: web.py application instance.
    :param kw: CORS options (origin, credentials, methods, headers, max_age,
        attach_to_all, automatic_options).
    :returns: Decorator function.

    .. seealso::
        https://developer.mozilla.org/en-US/docs/Web/HTTP/Access_control_CORS
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
    """Wrap a Flask controller with CORS headers.

    Especially useful for views using resources from many websites.

    :param app: Flask application instance.
    :param kw: CORS options (origin, credentials, methods, headers, max_age,
        attach_to_all, automatic_options).
    :returns: Decorator function.
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
    """Decorator that checks if user meets an auth criterion.

    Works with both web.py and Flask frameworks.

    :param checker_fn: Callable that returns True if authorized.
    :param fallback_fn: Callable to invoke if not authorized.
    :returns: Decorator function.
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
    """Generate cross-site request forgery protection token.

    :returns: XSRF token string.
    :rtype: str

    .. note::
        TODO: Add the xsrf tokens to forms.
    """
    if 'xsrf' not in web.ctx.session:
        web.ctx.session.xsrf = uuid.uuid4().hex  # better use sha?
    return web.ctx.session.xsrf


def xsrf_protected(fn):
    """Decorator protecting PUT/POST requests from session riding.

    :param fn: Function to protect.
    :returns: Wrapped function.

    .. note::
        TODO: Decorate controllers for xsrf protected forms.
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
    """Check if key has valid format.

    Validates format only (alphanumeric, underscore, hyphen, 1-255 chars).
    For user validation, integrate with your user model's key validation.

    :param str key: API key to validate.
    :returns: True if key format is valid.
    :rtype: bool
    """
    if not key:
        return False
    return VALID_KEY.fullmatch(key) is not None


def requires_api_key(fn):
    """Decorator requiring valid API key for controller access.

    Protects against directory traversal attacks and permission issues.

    :param fn: Controller function to protect.
    :returns: Wrapped function.
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
    """Generate URL with query parameters.

    Inspired by ``werkzeug.urls.Href``. Assumes traditional multiple params
    (does not overwrite). Use ``__replace__`` to overwrite params.
    Use ``__ignore__`` to filter out certain params.

    :param str path: Base URL path.
    :param params: Query parameters.
    :returns: Complete URL with query string.
    :rtype: str

    Example::

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
    """Add prefixes to web.py URL mappings.

    :param str pathpfx: Prefix for URL paths.
    :param str classpfx: Prefix for class names.
    :param tuple urls: web.py URL mapping tuple.
    :returns: New URL mapping tuple with prefixes.
    :rtype: tuple
    """
    newurls = []
    for i in range(0, len(urls), 2):
        newurls.extend((pathpfx + urls[i], classpfx + urls[i + 1]))
    return tuple(newurls)


def url_path_join(*parts):
    """Normalize URL parts and join them with a slash.

    :param parts: URL parts to join.
    :returns: Joined URL string.
    :rtype: str
    """
    schemes, netlocs, paths, queries, fragments = zip(*(urlsplit(part) for part in parts))
    scheme, netloc, query, fragment = first_of_each(schemes, netlocs, queries, fragments)
    path = '/'.join(x.strip('/') for x in paths if x)
    return urlunsplit((scheme, netloc, path, query, fragment))


def first_of_each(*sequences):
    """Return first non-empty element from each sequence.

    :param sequences: Variable number of sequences.
    :returns: Generator yielding first non-empty element from each.
    """
    return (next((x for x in sequence if x), '') for sequence in sequences)


_os_alt_seps: list[str] = [
    sep for sep in [os.sep, os.path.altsep] if sep is not None and sep != '/'
]


def safe_join(directory: str, *pathnames: str) -> str | None:
    """Safely join untrusted path components to a base directory.

    Prevents escaping the base directory via path traversal.

    :param str directory: The trusted base directory.
    :param pathnames: The untrusted path components relative to base.
    :returns: A safe path, or ``None`` if path would escape base.
    :rtype: str | None

    .. note::
        Via github.com/mitsuhiko/werkzeug security.py
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
                or pathlib.Path(filename).is_absolute()
                or filename == '..'
                or filename.startswith('../')):
            return None
        parts.append(filename)
    return posixpath.join(*parts)


def local_or_static_join(static, somepath):
    """Find template in working directory or static folder.

    :param str static: Static folder path.
    :param str somepath: Relative path to template.
    :returns: Full path to existing template.
    :rtype: Path
    :raises OSError: If template not found in either location.
    """
    localpath = expandabspath(somepath)
    if localpath.exists():
        return localpath
    staticjoin = safe_join(static, somepath)
    if staticjoin:
        staticpath = pathlib.Path(staticjoin)
        if staticpath.exists():
            return staticpath
    raise OSError('That template does not exist on your path or in the local package.')


def inject_file(x):
    """Read file contents for injection into HTML email templates.

    :param str x: Path to file (CSS, JS, etc.).
    :returns: File contents.
    :rtype: str
    """
    with pathlib.Path(x).open(encoding=None) as f:
        return f.read()


def inject_image(x):
    """Generate base64 data URI for image embedding in HTML.

    :param str x: Path to image file.
    :returns: Data URI string for use in img src attribute.
    :rtype: str
    """
    _, ext = os.path.splitext(x)
    with pathlib.Path(x).open('rb') as f:
        code = base64.b64encode(f.read())
        return f"data:image/{ext.strip('.')};base64,{code}"


def build_breadcrumb(ctx):
    """Build breadcrumb HTML from web.py app_stack.

    :param ctx: web.py context object.
    :returns: HTML string with breadcrumb links.
    :rtype: str
    """
    paths = [x.fvars.get('breadcrumb', '') for x in web.ctx.app_stack]
    names = [' '.join(_.title() for _ in path.strip('/').split('_')) for path in paths]
    paths[0], names[0] = ctx.realhome, 'Home'
    paths = accumulate(paths)
    pathsnames = list(zip(paths, names))
    links = list(starmap('<a href="{}/">{}</a>'.format, pathsnames))
    to_render = ' >> '.join(links)
    return to_render


def breadcrumbify(url_app_tuple):
    """Patch URL mapping into web.py subapps for breadcrumbs.

    :param tuple url_app_tuple: web.py style URL mapping.
    :returns: Modified URL mapping with breadcrumb info.
    :rtype: list
    """
    url_app_tuple = list(collapse(url_app_tuple))
    for i, app_or_url in enumerate(url_app_tuple):
        if isinstance(app_or_url, web.application):
            app_or_url.fvars['breadcrumb'] = url_app_tuple[i - 1]
    return url_app_tuple


def _format_link(cls):
    """Format link text for subapps in URL mapping.

    For ``web.application`` instances, returns the ``__name__`` of the
    parent module from the ``fvars`` attribute.

    :param cls: Class or web.application instance.
    :returns: Formatted link text.
    :rtype: str
    """
    if isinstance(cls, web.application):
        return splitcap(cls.fvars['__name__'])
    return splitcap(str(cls))


def appmenu(urls, home='', fmt=_format_link):
    """Build HTML menu from web.py URL mapping.

    :param tuple urls: web.py (name, link) tuple.
    :param str home: Home path prefix.
    :param fmt: Formatter function for link text.
    :returns: HTML unordered list string.
    :rtype: str
    """
    links = (
        f"    <li><a href=\"{urllib.parse.urljoin(home, link.strip('/') + '/')}\">{fmt(name)}</a></li>\n"
        for link, name in grouper(collapse(urls), 2)
    )
    return f"<ul class=\"menu\">\n{''.join(links)}</ul>"


def scale(color, pct):
    """Scale a hex color by a percentage.

    :param str color: Hex color string (e.g., '#FFF' or '#FFFFFF').
    :param float pct: Scale factor (1.0 = no change).
    :returns: Scaled hex color string.
    :rtype: str
    """
    def clamp(l, x, h):
        return min(max(l, x), h)

    if len(color) == 4:
        r, g, b = color[1], color[2], color[3]
        r += r
        g += g
        b += b
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
    """Render form field with error styling.

    Works with both web.py and Django forms.

    :param field: Form field object.
    :returns: HTML string for rendered field.
    :rtype: str
    """

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


def login_protected(priv_level=3, login_level=1):
    """Decorator protecting routes by session authentication.

    :param int priv_level: Required privilege level (default 3).
    :param int login_level: Required login level (default 1).
    :returns: Decorator function.
    """

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
    """Decorator limiting access to own user ID unless admin.

    :param fn: Function to protect.
    :returns: Wrapped function.
    """

    def dec_fn(*args, **kwargs):
        user_id = args[1]  # userid first REST arg for user manip
        if web.ctx.session['priv'] == 3 or int(user_id) == web.ctx.session['id']:
            return fn(*args, **kwargs)
        raise web.forbidden

    return dec_fn


def manager_or_admin(fn):
    """Decorator limiting access to managed resources unless admin.

    :param fn: Function to protect.
    :returns: Wrapped function.
    """

    def dec_fn(*args, **kwargs):
        disease_id = args[1]  # diseaseid first REST arg for dis manip
        if web.ctx.session['priv'] == 3 or int(disease_id) == web.ctx.session['manages']:
            return fn(*args, **kwargs)
        raise web.forbidden

    return dec_fn


class JSONEncoderISODate(json.JSONEncoder):
    """JSON encoder that serializes dates in ISO format.

    Example::

        >>> JSONEncoderISODate().encode({'dt': datetime.date(2014, 10, 2)})
        '{"dt": "2014-10-02"}'
    """

    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


class JSONDecoderISODate(json.JSONDecoder):
    """JSON decoder that parses date strings into datetime objects.

    Example::

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
    """WSGI middleware for profiling requests.

    :param func: WSGI application callable.
    :param log: Logger instance for output.
    :param str sort: Profile sort key (default 'time').
    :param int count: Number of top functions to show (default 20).

    .. warning::
        Should always be last middleware loaded:
        1. You want to profile everything else
        2. For speed, we return the result NOT the wrapped func
    """

    def __init__(self, func, log=None, sort='time', count=20):
        self.func = func
        self.log = log
        self.sort = sort
        self.count = count

    def __call__(self, environ, start_response):
        stime = time.time()
        pr = cProfile.Profile()
        result = pr.runcall(self.func, environ, start_response)
        etime = time.time() - stime
        self.log.info(f'Run finished in {etime} seconds')

        with io.StringIO() as s:
            ps = pstats.Stats(pr, stream=s).sort_stats(self.sort)
            ps.print_stats(self.count)
            self.log.debug(s.getvalue())

        return result


def logerror(olderror, logger):
    """Wrap internalerror function to log tracebacks.

    :param olderror: Original error handler function.
    :param logger: Logger instance for error output.
    :returns: Wrapped error handler.
    """

    def logerror_fn():
        _, exc, _ = sys.exc_info()
        theerr = olderror()
        if exc is not None:
            logger.error(exc)
        return theerr

    return logerror_fn


def validip6addr(address):
    """Check if address is a valid IPv6 address.

    :param str address: Address string to validate.
    :returns: True if valid IPv6 address.
    :rtype: bool

    Example::

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
    except (OSError, AttributeError, ValueError):
        return False

    return True


def validipaddr(address):
    """Check if address is a valid IPv4 address.

    :param str address: Address string to validate.
    :returns: True if valid IPv4 address.
    :rtype: bool

    Example::

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
    """Check if port is a valid port number.

    :param str port: Port string to validate.
    :returns: True if valid port (0-65535).
    :rtype: bool

    Example::

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
    """Parse IP address and port from string.

    :param str ip: IP address string (with optional port).
    :param str defaultaddr: Default address if not specified.
    :param int defaultport: Default port if not specified.
    :returns: Tuple of (ip_address, port).
    :rtype: tuple
    :raises ValueError: If invalid IP address/port format.

    Example::

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
    """Parse address as IP:port tuple or Unix socket path.

    :param str string_: Address string to parse.
    :returns: (ip_address, port) tuple or socket path string.
    :raises ValueError: If invalid format.

    Example::

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
    """Quote string for safe use in a URL.

    :param val: String to quote (or None).
    :returns: URL-encoded string.
    :rtype: str

    Example::

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
    """Format datetime object for HTTP headers.

    :param date_obj: datetime object to format.
    :returns: HTTP date string in RFC 1123 format.
    :rtype: str

    Example::

        >>> import datetime
        >>> httpdate(datetime.datetime(1970, 1, 1, 1, 1, 1))
        'Thu, 01 Jan 1970 01:01:01 GMT'
    """
    return date_obj.strftime('%a, %d %b %Y %H:%M:%S GMT')


def parsehttpdate(string_):
    """Parse HTTP date string into datetime object.

    :param str string_: HTTP date string in RFC 1123 format.
    :returns: Parsed datetime object, or None if invalid.
    :rtype: datetime.datetime | None

    Example::

        >>> parsehttpdate('Thu, 01 Jan 1970 01:01:01 GMT')
        datetime.datetime(1970, 1, 1, 1, 1, 1)
    """
    try:
        t = time.strptime(string_, '%a, %d %b %Y %H:%M:%S %Z')
    except ValueError:
        return None
    return datetime.datetime(*t[:6])


def htmlquote(text):
    r"""Encode text for safe use in HTML.

    :param str text: Text to encode.
    :returns: HTML-encoded string.
    :rtype: str

    Example::

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
    r"""Decode HTML-encoded text.

    :param str text: HTML-encoded string.
    :returns: Decoded text.
    :rtype: str

    Example::

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
    r"""Convert value to safe Unicode HTML string.

    :param val: Value to convert (string, bytes, or None).
    :returns: HTML-safe string.
    :rtype: str

    Example::

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
