##############################################################################
#
# Copyright (c) 2006 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""Buildout package
"""
import os
import sys
from setuptools.package_index import PackageIndex
from setuptools.package_index import URL_SCHEME
from setuptools.package_index import HREF
from setuptools.package_index import distros_for_url
from setuptools.package_index import htmldecode

from pip._internal.index.collector import HTMLPage
from pip._internal.index.collector import parse_links
from pip._internal.index.collector import _clean_link
from pip._internal.index.package_finder import _check_link_requires_python
from pip._internal.models.target_python import TargetPython
from pip._vendor import six
from pip._vendor.six.moves import urllib


def patch_Distribution():
    try:
        from pkg_resources import _remove_md5_fragment
        from pkg_resources import Distribution

        if hasattr(Distribution, 'location'):
            return

        # prepare any Distribution built before monkeypatch
        from pkg_resources import working_set
        for dist in working_set:
            dist._location = dist.location
            dist._location_without_md5 = _remove_md5_fragment(dist.location)

        def hashcmp(self):
            without_md5 = getattr(self, '_location_without_md5', '')
            return (
                self.parsed_version,
                self.precedence,
                self.key,
                without_md5,
                self.py_version or '',
                self.platform or '',
            )

        def get_location(self):
            try:
                result = self._location
            except AttributeError:
                result = ''
            return result

        def set_location(self, l):
            self._location = l
            self._location_without_md5 = _remove_md5_fragment(l)

        setattr(Distribution, 'location', property(get_location, set_location))
        setattr(Distribution, 'hashcmp', property(hashcmp))
    except ImportError:
        return


patch_Distribution()


def setup_coverage():
    if not 'RUN_COVERAGE' in os.environ:
        return
    if ('COVERAGE_PROCESS_START' not in os.environ):
        os.environ['COVERAGE_PROCESS_START'] = os.path.abspath('../../.coveragerc')
    coveragerc = os.getenv('COVERAGE_PROCESS_START')
    if coveragerc:
        try:
            import coverage
            print("Coverage configured with %s" % coveragerc)
            coverage.process_startup()
        except ImportError:
            print("You try to run coverage but coverage is not installed in your virtualenv.")
            sys.exit(1)


PY_VERSION_INFO = TargetPython().py_version_info






def patch_PackageIndex():
    setattr(PackageIndex, 'process_url', process_url)


def process_url(self, url, retrieve=False):
    """Evaluate a URL as a possible download, and maybe retrieve it"""
    if url in self.scanned_urls and not retrieve:
        return
    self.scanned_urls[url] = True
    if not URL_SCHEME(url):
        self.process_filename(url)
        return
    else:
        dists = list(distros_for_url(url))
        if dists:
            if not self.url_ok(url):
                return
            self.debug("Found link: %s", url)

    if dists or not retrieve or url in self.fetched_urls:
        list(map(self.add, dists))
        return  # don't need the actual page

    if not self.url_ok(url):
        self.fetched_urls[url] = True
        return

    self.info("Reading %s", url)
    self.fetched_urls[url] = True  # prevent multiple fetch attempts
    tmpl = "Download error on %s: %%s -- Some packages may not be found!"
    f = self.open_url(url, tmpl % url)
    if f is None:
        return
    if isinstance(f, urllib.error.HTTPError) and f.code == 401:
        self.info("Authentication error: %s" % f.msg)
    self.fetched_urls[f.url] = True
    if 'html' not in f.headers.get('content-type', '').lower():
        f.close()  # not html, we can't process it
        return

    base = f.url  # handle redirects
    page = f.read()
    if isinstance(page, six.text_type):
        page = page.encode('utf8')
        charset = 'utf8'
    else:
        if isinstance(f, urllib.error.HTTPError):
            # Errors have no charset, assume latin1:
            charset = 'latin-1'
        else:
            try:
                charset = f.headers.get_param('charset') or 'latin-1'
            except AttributeError:
                # Python 2
                charset = f.headers.getparam('charset') or 'latin-1'
    try:
        html_page = HTMLPage(page, charset, base, cache_link_parsing=False)
    except TypeError:
        html_page = HTMLPage(page, charset, base)

    plinks = list(parse_links(html_page))
    pip_links = [l.url for l in plinks]
    if not isinstance(page, str):
        # In Python 3 and got bytes but want str.
        page = page.decode(charset, "ignore")
    f.close()

    links = []
    for match in HREF.finditer(page):
        link = urllib.parse.urljoin(base, htmldecode(match.group(1)))
        links.append(_clean_link(link))

    # TODO: remove assertion and double index page parsing before releasing.
    assert set(pip_links) == set(links)

    for link in plinks:
        if _check_link_requires_python(link, PY_VERSION_INFO):
            self.process_url(link.url)

    if url.startswith(self.index_url) and getattr(f, 'code', None) != 404:
        page = self.process_index(url, page)


patch_PackageIndex()


class UserError(Exception):
    """Errors made by a user
    """

    def __str__(self):
        return " ".join(map(str, self.args))
