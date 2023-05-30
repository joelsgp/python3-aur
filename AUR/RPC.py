#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2009-2021 Xyne
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# (version 2) as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


"""
Retrieve data from the AUR via the RPC interface.

Results are cached in an SQLite3 database to avoid redundant queries when
practical.

For more information see https://aur.archlinux.org/rpc.php and
https://projects.archlinux.org/aurweb.git/plain/doc/rpc.txt
"""

import argparse
import json
import logging
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import warnings

from html.parser import HTMLParser

import xdg.BaseDirectory

import MemoizeDB
import XCGF
import XCPF

import AUR.common


# --------------------------------- Globals ---------------------------------- #

RPC_URL = AUR.common.AUR_URL + "/rpc.php"
RPC_VERSION = 5
RPC_MAX_ARGS = 500
CODING = "UTF-8"

# Valid parameters for the chosen version of the RPC interface.
RPC_TYPES = ("info", "search")
RPC_BYS = ("name", "name-desc", "maintainer")
RPC_DEFAULT_BY = RPC_BYS[1]


INTEGER_FIELDS = (
    "FirstSubmitted",
    "ID",
    "LastModified",
    "NumVotes",
    "OutOfDate",
    "PackageBaseID",
)

LIST_FIELDS = (
    "CheckDepends",
    "Conflicts",
    "Depends",
    "Groups",
    "Keywords",
    "License",
    "MakeDepends",
    "OptDepends",
    "Provides",
    "Replaces",
    "Source",
)

URL_FIELDS = (
    "URL",
    "AURPage",
    "URLPath",
)
DISPLAY_FIELDS = (
    "PackageBase",
    "Name",
    "Version",
    "Description",
    "URL",
    "URLPath",
    "Maintainer",
    "Depends",
    "MakeDepends",
    "CheckDepends",
    "OptDepends",
    "Conflicts",
    "Provides",
    "Replaces",
    "Groups",
    "License",
    "NumVotes",
    "FirstSubmitted",
    "LastModified",
    "LastPackager",
    "OutOfDate",
    "ID",
    "PackageBaseID",
    "Keywords",
)


# ----------------------------- List Formatting ------------------------------ #


def lst_to_txt(lst):
    """
    Prepare a list for storage in a text field.
    """
    return "\n".join(lst)


def txt_to_lst(txt):
    """
    Convert a textified list back to a list.
    """
    if txt:
        return txt.split("\n")
    else:
        return list()


# --------------------------------- RPC URL ---------------------------------- #


def rpc_url(typ, args, by=RPC_DEFAULT_BY, post=False):
    """
    Format the RPC URL.
    """
    qs = [("v", RPC_VERSION), ("type", typ)]
    if typ == "info":
        param = "arg[]"
    elif typ == "search":
        param = "arg"
        qs.append(("by", by))
    else:
        param = "arg"
    qs.extend((param, a) for a in args)
    qs_str = urllib.parse.urlencode(qs)
    if post:
        return RPC_URL, qs_str.encode(CODING)
    else:
        return "{}?{}".format(RPC_URL, qs_str)


# ------------------------------ HTML Scraping ------------------------------- #

# This is a temporary page scraper to get the last packager which is currently
# omitted from the RPC info.


class LastPackagerParser(HTMLParser):
    """
    Parse the last packager from the AUR package page.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_pkginfo = False
        self.in_th = False
        self.in_last_packager = False
        self.last_packager = None

    def handle_starttag(self, tag, attrs):
        if tag == "table" and ("id", "pkginfo") in attrs:
            self.in_pkginfo = True
        elif not self.in_pkginfo:
            return

        if tag == "th":
            self.in_th = True
        elif self.in_last_packager and tag == "a":
            self.in_last_packager = True

    def handle_endtag(self, tag):
        self.in_th = False
        if tag == "table":
            self.in_pkginfo = False
        if tag == "td":
            self.in_last_packager = False

    def handle_data(self, data):
        if self.in_th and data.strip() == "Last Packager:":
            self.in_last_packager = True
        elif self.in_last_packager:
            self.last_packager = data.strip()


def add_last_packager(pkg):
    """
    Get the last packager by scraping the AUR webpage of the given package.
    """
    url = AUR.common.AUR_URL + f"""/packages/{urllib.parse.quote_plus(pkg['Name'])}"""
    with urllib.request.urlopen(url) as f:
        html_code = f.read().decode()
    parser = LastPackagerParser()
    parser.feed(html_code)
    pkg["LastPackager"] = parser.last_packager


# ----------------------------------- AUR ------------------------------------ #


def insert_full_urls(pkgs):
    """
    Replace partial URLS with full URLS for each passed package.
    """
    for pkg in pkgs:
        try:
            if not pkg["URLPath"].startswith(AUR.common.AUR_URL):
                pkg["URLPath"] = AUR.common.AUR_URL + pkg["URLPath"]
        except (KeyError, TypeError):
            pass
        yield pkg


def convert_pkginfo(pkg):
    """
    Convert package info fields to expected formats.
    """

    for key in INTEGER_FIELDS:
        try:
            if pkg[key] is None:
                continue
            pkg[key] = int(pkg[key])
        except KeyError:
            pass
        except TypeError:
            logging.error("failed to convert {} to integer ({})".format(key, pkg[key]))
    #   for key in LIST_FIELDS:
    #     if key not in pkg:
    #       pkg[key] = list()
    return pkg


def format_rpc_args(args):
    """
    Ensure that the arguments are a list. If None, then a list with a single empty
    string will be returned to ensure that e.g. orphan searches work as expected.
    """
    if args is None:
        return ("",)
    elif isinstance(args, str):
        return (args,)
    else:
        return tuple(a if a is not None else "" for a in args)


def rpc_info(args):
    """
    MemoizeDB glue function for RPC info queries.
    """
    for pkg in aur_query("info", args):
        yield pkg["Name"], (json.dumps(pkg),)


def rpc_search_by(args, by=RPC_DEFAULT_BY):
    """
    MemoizeDB glue function for RPC search queries.
    """
    for arg in args:
        hits = list(aur_query("search", (arg,), by=by))
        if hits:
            yield arg, (json.dumps(hits),)
        else:
            yield arg, None


def aur_query(typ, args, by=RPC_DEFAULT_BY):
    """
    Query the AUR RPC interface.
    """
    for r in _aur_query_wrapper(typ, format_rpc_args(args), by=by):
        yield r


def _aur_query_wrapper(typ, args, by=RPC_DEFAULT_BY):
    """
    Internal function. This will split long query strings when necessary to
    retrieve all of the results.
    """
    url = rpc_url(typ, args, by=by)
    try:
        for r in _aur_query(typ, url):
            yield r
    except urllib.error.HTTPError as e:
        # URI Too Long
        if e.code == 414:
            logging.debug(str(e))
            n = len(args)
            i = math.ceil(n / 2)
            for r in _aur_query_wrapper(typ, args[:i], by=by):
                yield r
            if i < n:
                for r in _aur_query_wrapper(typ, args[i:], by=by):
                    yield r
        else:
            logging.error(str(e))
            raise e


def _aur_query(typ, url, post_data=None):
    """
    Internal function. Iterate over results.
    """
    logging.debug("retrieving {}".format(url))
    with urllib.request.urlopen(url, data=post_data) as f:
        response = json.loads(f.read().decode(CODING))
    logging.debug(json.dumps(response, indent="  ", sort_keys=True))
    try:
        rtyp = response["type"]
        if rtyp == typ or (rtyp == "multiinfo" and typ == "info"):
            if response["resultcount"] == 0:
                logging.info("no results found")
                return
            for r in response["results"]:
                yield r
        elif rtyp == "error":
            logging.error("RPC error {}".format(response["results"]))
        else:
            logging.error("Unexpected RPC return type {}".format(rtyp))
    except KeyError:
        logging.error("Unexpected RPC error.")


# ------------------------------ AurError Class ------------------------------ #


class AurError(Exception):
    """
    Exception raised by AUR objects.
    """

    def __init__(self, msg, error=None):
        self.msg = msg
        self.error = error


# -------------------------------- AUR Class --------------------------------- #


class AurRpc(object):
    """
    Interact with the Arch Linux User Repository (AUR)

    Data retrieved via the RPC interface is cached temporarily in an SQLite3
    database to avoid unnecessary remote calls.
    """

    def __init__(
        self, database=None, mdb=None, ttl=AUR.common.DEFAULT_TTL, clean=False
    ):
        """
        Initialize the AUR object.

        database:
          SQLite3 database path. Leave as None to use the default path. Use
          ":memory:" to avoid creating a cache file. default:
          $XDG_CACHE_HOME/AUR/RPC.sqlite3

        ttl:
          Time to live, i.e. how long to cache individual results in the database.

        clean:
          Clean the database to remove old entries and ensure integrity.
        """

        if not database:
            cachedir = xdg.BaseDirectory.save_cache_path(AUR.common.XDG_NAME)
            database = os.path.join(cachedir, "RPC.sqlite3")

        if mdb is None:
            glue = {"info": (rpc_info, (("data", "TEXT"),), ttl)}

            for by in RPC_BYS:
                table = "search_by_{}".format(by.replace("-", "_"))

                # by=by is required to bind the function and ensure that all 3 are
                # different.
                def f(xs, by=by):
                    return rpc_search_by(xs, by=by)

                glue[table] = (f, (("data", "TEXT"),), ttl)

            conn = sqlite3.connect(
                database,
                detect_types=(sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES),
                isolation_level=None,
            )
            mdb = MemoizeDB.MemoizeDB(conn, glue)
            mdb.db_initialize()

        elif clean:
            mdb.db_clean()

        self.mdb = mdb

    # ------------------------ Accessibility Methods ------------------------ #

    def get(self, *args, **kwargs):
        """
        See the documentation for _get.
        """
        for pkg in self._get(*args, **kwargs):
            yield convert_pkginfo(pkg)

    def _get(self, typ, args, by=RPC_DEFAULT_BY, intersect=False, last_packager=False):
        """
        Get package information from the AUR RPC interface using locally cached
        data when available and still valid.

        Yields a generator over the returned packages.

        Args:
            by:
                The field by which to search.

            intersect:
                If True, only packages matching all search terms are returned.

            last_packager:
                If True, scrape the last packager from the AUR website when
                returning info.
        """
        if args is not None and not args:
            return

        if typ == "info":
            table = "info"
        elif typ == "search":
            if by in RPC_BYS:
                table = "search_by_{}".format(by.replace("-", "_"))
            else:
                raise AurError('unrecognized "by": {}'.format(by))
        else:
            raise AurError("unrecognized operation: {}".format(typ))

        if typ == "info":
            # Determine the names of packages for which information must be retrieved.
            # by stripping version requirements from the names. Once the data has been
            # retrieved, the version requirements will be checked and only those
            # packages which satisfy all given requirements will be returned.
            arg_set = set(args)
            ver_reqs = XCPF.collect_version_requirements(arg_set)
            names = set(ver_reqs)
            for pkg in self.mdb.get_nth_field_many(table, format_rpc_args(names)):
                if pkg is None:
                    continue
                pkg = json.loads(pkg)
                if last_packager:
                    add_last_packager(pkg)
                if XCPF.satisfies_all_version_requirements(
                    pkg["Version"], ver_reqs[pkg["Name"]]
                ):
                    yield pkg

        else:
            if intersect:
                n = 0
                hits = dict()
                for results in self.mdb.get_nth_field_many(
                    table, format_rpc_args(args)
                ):
                    n += 1
                    for pkg in json.loads(results):
                        try:
                            hit = hits[pkg["Name"]]
                        except KeyError:
                            hits[pkg["Name"]] = (1, pkg)
                        else:
                            hits[pkg["Name"]] = (hit[0] + 1, pkg)
                for count, pkg in hits.values():
                    if count == n:
                        yield pkg
            else:
                for results in self.mdb.get_nth_field_many(
                    table, format_rpc_args(args)
                ):
                    if results is not None:
                        for pkg in json.loads(results):
                            yield pkg

    def info(self, *args, **kwargs):
        """
        Retrieve package information.
        """
        return self.get("info", *args, **kwargs)

    def search(self, *args, by=RPC_DEFAULT_BY, intersect=False, **kwargs):
        """
        Search for packages.
        """
        return self.get("search", *args, by=by, intersect=intersect, **kwargs)

    def msearch(self, *args, **kwargs):
        """
        Search for packages by maintainer. Only the names are returned.
        """
        warnings.warn("deprecated", category=DeprecationWarning)
        return self.get("search", *args, by="maintainer", **kwargs)


# --------------------------------- Download --------------------------------- #


def download_archives(output_dir, pkgs):
    """
    Download the AUR files to the target directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    for pkg in insert_full_urls(pkgs):
        logging.debug(
            "Retrieving and extracting {} to {}.".format(pkg["URLPath"], output_dir)
        )
        with urllib.request.urlopen(pkg["URLPath"]) as f:
            logging.debug("extracting {} to {}".format(pkg["URLPath"], output_dir))
            tarfile.open(mode="r|gz", fileobj=f).extractall(path=output_dir)
        yield pkg


def download_git_repo(output_dir, pkgs, warn=False, pull=False):
    """
    Download the AUR files to the target directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    for pkg in pkgs:
        git_url = AUR.common.AUR_GIT_URL_FORMAT.format(
            urllib.parse.quote_plus(pkg["PackageBase"])
        )
        repo_dir = os.path.join(output_dir, pkg["PackageBase"])

        if os.path.isdir(repo_dir):
            if pull:
                cmd = ["git", "-C", repo_dir, "pull"]
            else:
                cmd = ["git", "-C", repo_dir, "fetch"]
        else:
            cmd = ["git", "clone", git_url, repo_dir]
        logging.debug("running {}".format(XCGF.sh_quote_words(cmd)))
        try:
            subprocess.run(cmd, stderr=subprocess.PIPE, check=True)
            if not os.path.exists(os.path.join(repo_dir, "PKGBUILD")):
                shutil.rmtree(repo_dir)
                raise RuntimeError("probably no repo")
            with open(os.path.join(repo_dir, ".SRCINFO"), "r") as handle:
                pkg["Names"] = list(
                    line.split("=")[1].strip()
                    for line in handle
                    if line.startswith("pkgname =")
                )
            yield pkg
        except (subprocess.CalledProcessError, RuntimeError) as e:
            f = logging.warn if warn else logging.error
            f("failed to clone or fetch {} to {} [{}]".format(git_url, repo_dir, e))


# ----------------------------- User Interaction ----------------------------- #


def parse_args(args=None):
    """
    Parse command-line arguments.

    If no arguments are passed then arguments are read from sys.argv.
    """
    parser = argparse.ArgumentParser(
        description="Query the AUR RPC interface.",
        epilog="For maintainer searches, use an empty string ('') as an argument to search for orphans.",
    )
    parser.add_argument("args", metavar="<arg>", nargs="+")
    parser.add_argument(
        "-i", "--info", action="store_true", help="Query package information."
    )
    parser.add_argument("-s", "--search", action="store_true", help="Search the AUR.")
    parser.add_argument(
        "--by",
        choices=RPC_BYS,
        default=RPC_DEFAULT_BY,
        help="By which fields to search. Default: %(default)s",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debugging.")
    parser.add_argument(
        "--log", metavar="<path>", help="Log debugging information to <path>."
    )
    parser.add_argument(
        "--ttl",
        metavar="<minutes>",
        type=int,
        default=(AUR.common.DEFAULT_TTL // 60),
        help="Time-to-live of cached data (default: %(default)s)",
    )
    parser.add_argument(
        "--full-info",
        action="store_true",
        help="Return full information for searches and msearches.",
    )
    parser.add_argument(
        "--intersect",
        action="store_true",
        help="When searching for packages, only return results that match all search terms.",
    )
    return parser.parse_args(args)


def format_pkginfo(pkgs):
    """
    Format package information for display similarly to "pacman -Si".

    This function modifies the passed packages.
    """
    fields = list(DISPLAY_FIELDS)
    fields.insert(0, "Repository")
    fields.insert(6, "AURPage")
    # +1 for space, +1 for _ separator for arch-specific fields
    w = max(map(len, fields)) + 2 + max(map(len, XCPF.ARCHLINUX_OFFICIAL_ARCHITECTURES))
    fmt = "{{:<{:d}s}}: {{!s:<s}}\n".format(w)

    for pkg in insert_full_urls(sorted(pkgs, key=lambda p: p["Name"])):
        info = ""
        pkg["Repository"] = "AUR"
        pkg["AURPage"] = AUR.common.AUR_URL + "/packages/{}".format(
            urllib.parse.quote_plus(pkg["Name"])
        )
        if pkg["OutOfDate"] is not None:
            pkg["OutOfDate"] = time.strftime(
                XCGF.DISPLAY_TIME_FORMAT, time.localtime(pkg["OutOfDate"])
            )
        else:
            pkg["OutOfDate"] = ""
        for foo in ("FirstSubmitted", "LastModified"):
            pkg[foo] = time.strftime(XCGF.DISPLAY_TIME_FORMAT, time.localtime(pkg[foo]))
        for f in fields:
            if f in LIST_FIELDS:
                names = [f]
                names.extend(
                    "{}_{}".format(f, a) for a in XCPF.ARCHLINUX_OFFICIAL_ARCHITECTURES
                )
                for n in names:
                    try:
                        value = XCPF.format_pkginfo_list(
                            pkg[n],
                            per_line=(f in ("OptDepends",)),
                            margin=w + 2,
                        )
                        info += fmt.format(n, value)
                    except KeyError:
                        if n == f:
                            info += fmt.format(f, "None")
            else:
                try:
                    if isinstance(pkg[f], str):
                        txt = pkg[f]
                    else:
                        txt = str(pkg[f])
                        if f not in URL_FIELDS:
                            txt = XCPF.format_pkginfo_string(txt, margin=w + 2)
                    info += fmt.format(f, txt)
                except KeyError:
                    pass
        yield info


def main(args=None):
    """
    Parse command-line arguments and print query results to STDOUT.
    """
    pargs = parse_args(args)

    if pargs.debug:
        log_level = logging.DEBUG
    else:
        log_level = None
    XCGF.configure_logging(level=log_level, log=pargs.log)

    ttl = max(pargs.ttl, 0) * 60
    aur = AurRpc(ttl=ttl)
    if pargs.info:
        pkgs = aur.info(pargs.args, last_packager=False)
    else:
        if pargs.by == "maintainer":
            pargs.args = list(m if m else None for m in pargs.args)
        pkgs = aur.search(pargs.args, by=pargs.by, intersect=pargs.intersect)
    for info in format_pkginfo(pkgs):
        print(info)


def run_main(args=None):
    """
    Run main() with exception handling.
    """
    try:
        main(args)
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    except AurError as e:
        sys.exit("error: {}".format(e.msg))
    except urllib.error.URLError as e:
        sys.exit("URLError: {}".format(e))


if __name__ == "__main__":
    run_main()
