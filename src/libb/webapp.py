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
import sys
import time
import urllib.parse
from functools import update_wrapper, wraps
from typing import Callable

from dateutil import parser

from libb import expandabspath, grouper, splitcap

with contextlib.suppress(ImportError):
    import flask

logger = logging.getLogger(__name__)

__all__ = [
    'authd',
    'make_url',
    'appmenu',
    'render_field',
    'scale',
    'safe_join',
    'local_or_static_join',
    'inject_file',
    'inject_image',
    'htmlquote',
    'websafe',
    'rsleep',
    'rand_retry',
    'logerror',
    'COOKIE_DEFAULTS',
    'JSONEncoderISODate',
    'JSONDecoderISODate',
    'Jinja2Render',
    'ProfileMiddleware',
    'get_request_dict',
    'is_safe_redirect_url',
    'external_url_for',
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


def authd(checker_fn, fallback_fn):
    """Decorator that checks if user meets an auth criterion.

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
# URL and path utility methods
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


def appmenu(urls: tuple, fmt_name: Callable | None = None) -> str:
    """Build HTML menu from URL/name pairs.

    :param urls: Tuple of alternating (url, name) pairs.
    :param fmt_name: Formatter for link text (default: splitcap).
    :returns: HTML unordered list string.
    """
    fmt_name = fmt_name or splitcap
    links = [
        f'    <li><a href="{url}">{fmt_name(name)}</a></li>'
        for url, name in grouper(urls, 2)
    ]
    return '<ul class="menu">\n' + '\n'.join(links) + '\n</ul>'


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


def render_field(field) -> str:
    """Render form field with error styling.

    :param field: Form field object.
    :returns: HTML string for rendered field.
    """

    def get_error(field):
        if hasattr(field, 'note'):
            return field.note
        if hasattr(field, 'errors'):
            return ', '.join(field.errors)
        return None

    html = []
    error = get_error(field)
    if error:
        html.append(f'<span class="flderr" title="{error}">')
    html.append(str(field))
    if error:
        html.append('</span>')
    return '\n'.join(html)


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


#
# Jinja2 rendering infrastructure (Flask-compatible)
#


class Jinja2Render:
    """Jinja2 render class.

    Usage::

        render = Jinja2Render('templates/')
        render.add_globals({'format': fmt, 'today': datetime.date.today})
        html = render('generic.html', title='Page', content=[html1, html2])
    """

    def __init__(
        self,
        template_dir: str,
        globals: dict | None = None,
        autoescape: bool = True,
    ) -> None:
        """Initialize Jinja2 environment with template directory.

        :param template_dir: Path to template directory.
        :param globals: Dict of global variables/functions for templates.
        :param autoescape: Enable HTML autoescaping (default True).
        """
        from jinja2 import Environment, FileSystemLoader

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=autoescape,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        if globals:
            self.env.globals.update(globals)

    def __call__(self, template_name: str, **context) -> str:
        """Render template with context - same signature as Flask's render_template.

        :param template_name: Name of template file (e.g., 'generic.html').
        :param context: Keyword arguments passed to template.
        :returns: Rendered HTML string.
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def add_globals(self, globals_dict: dict) -> None:
        """Add globals to Jinja2 environment.

        :param globals_dict: Dict of globals to add.
        """
        self.env.globals.update(globals_dict)

    def add_filter(self, name: str, func: callable) -> None:
        """Add custom filter to Jinja2 environment.

        :param name: Filter name to use in templates.
        :param func: Filter function.
        """
        self.env.filters[name] = func


def get_request_dict(**defaults) -> dict:
    """Get request parameters with defaults, supporting callables.

    Example::

        get_request_dict(fund='All', date=lambda: Date.today())

    :param defaults: Default values for parameters. Callables are invoked.
    :returns: Dict of request parameters with defaults applied.
    """
    req = {}
    try:
        if flask.has_request_context():
            req = flask.request.values.to_dict()
    except (NameError, AttributeError):
        pass

    for key, default in defaults.items():
        if key not in req or req[key] == '':
            req[key] = default() if callable(default) else default

    return req


def is_safe_redirect_url(url: str) -> bool:
    """Check if redirect URL is safe (relative path only, no protocol injection).

    :param url: URL to validate.
    :returns: True if URL is safe for redirect.

    Example::

        >>> is_safe_redirect_url('/login/')
        True
        >>> is_safe_redirect_url('//evil.com')
        False
        >>> is_safe_redirect_url('https://evil.com')
        False
        >>> is_safe_redirect_url('')
        False
    """
    if not url:
        return False
    return url.startswith('/') and not url.startswith('//')


def external_url_for(base_url: str, endpoint: str, **values) -> str:
    """Generate full URL with domain for external use (emails, etc).

    :param base_url: Base URL including scheme and domain (e.g. 'https://app.example.com').
    :param endpoint: Flask endpoint name.
    :param values: URL parameters passed to url_for.
    :returns: Complete URL.
    """
    return urllib.parse.urljoin(base_url, flask.url_for(endpoint, **values))


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
