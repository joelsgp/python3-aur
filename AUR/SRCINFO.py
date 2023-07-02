#!/usr/bin/env python

# Copyright (C) 2015  Xyne
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

import argparse
import json
import logging
import os.path
import re
import sqlite3
import sys
import urllib.parse

import xdg.BaseDirectory

import AUR.common
import MemoizeDB
import XCGF


################################### Globals ####################################

PKGBASE_STRING = "pkgbase"
PKGNAME_STRING = "pkgname"

SRCINFO_PATH = "/cgit/aur.git/plain/.SRCINFO?h={}"
PKGLIST_URL = AUR.common.AUR_URL + SRCINFO_PATH


################################## Functions ###################################


def srcinfo_dbpath():
    """
    Return a path to the .SRCINFO caching database.
    """
    cachedir = xdg.BaseDirectory.save_cache_path(AUR.common.XDG_NAME)
    return os.path.join(cachedir, "SRCINFO.sqlite3")


def srcinfo_url(pkgname):
    """
    Get the URL of the .SRCINFO file.
    """
    return PKGLIST_URL.format(urllib.parse.quote_plus(pkgname))


def insert_pkgbase(pkginfo, pkgbase):
    """
    Insert items from the pkgbase.
    """
    for bk, bv in pkgbase.items():
        if bk not in pkginfo:
            pkginfo[bk] = bv.copy()
        else:
            pkginfo[bk].extend(bv)
    return pkginfo


def parse_srcinfo(lines):
    """
    Parse the lines of a .SRCINFO file.
    """
    srcinfo = dict()
    obj = None

    for line in lines:
        stripped_line = line.strip()

        if not stripped_line or stripped_line[0] == "#":
            continue

        try:
            k, v = stripped_line.split(" = ", 1)
        except ValueError:
            logging.warning(
                'unexpected line while parsing SRCINFO: "{}" (expected format: "<key>=<value>")'.format(
                    line
                )
            )
            continue

        if line[0] == "\t":
            try:
                obj[k].append(v)
            except KeyError:
                obj[k] = [v]

        else:
            obj = dict()
            if k == PKGBASE_STRING:
                srcinfo[PKGBASE_STRING] = (v, obj)
            else:
                try:
                    srcinfo[k][v] = obj
                except KeyError:
                    srcinfo[k] = {v: obj}

    logging.debug(json.dumps(srcinfo, indent="  ", sort_keys=True))
    return srcinfo


def read_srcinfo_file(path):
    """
    Read a .SRCINFO file.
    """
    with open(path, "r") as f:
        return parse_srcinfo(f)


def read_srcinfo_url(url):
    """
    Read a .SRCINFO URL.
    """
    text = XCGF.text_from_url(url)
    return parse_srcinfo(text.split("\n"))


def get_pkginfo(srcinfo, pkgname):
    """
    Return package information for one of the packages within the SRCINFO.
    """
    try:
        pkginfo = srcinfo[PKGNAME_STRING][pkgname].copy()
        try:
            pkgbase = srcinfo[PKGBASE_STRING][0]
            pkginfo = insert_pkgbase(pkginfo, srcinfo[PKGBASE_STRING][1])
        except KeyError:
            pkgbase = pkgname
            pass
    except KeyError:
        return None
    pkginfo[PKGBASE_STRING] = pkgbase
    pkginfo[PKGNAME_STRING] = pkgname
    return pkginfo


################################## AurSrcInfo ##################################


class AurSrcinfo(object):
    """
    A caching AUR .SRCINFO retriever.
    """

    SRCINFO_TABLE = "srcinfo"

    def __init__(self, mdb=None, dbpath=None, ttl=AUR.common.DEFAULT_TTL):
        if mdb is None:
            if dbpath is None:
                dbpath = srcinfo_dbpath()

            def f(pkgnames):
                for pkgname in pkgnames:
                    url = srcinfo_url(pkgname)
                    try:
                        yield pkgname, (XCGF.text_from_url(url),)
                    except urllib.error.HTTPError as e:
                        if e.code == 404:
                            yield pkgname, None
                        else:
                            raise e

            glue = {self.SRCINFO_TABLE: (f, (("text", "TEXT"),), ttl)}
            conn = sqlite3.connect(
                dbpath,
                detect_types=(sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES),
                isolation_level=None,
            )
            mdb = MemoizeDB.MemoizeDB(conn, glue)
            mdb.db_initialize()
        self.mdb = mdb

    def get(self, args):
        """
        Iterate over the parse .SRCINFO files. Returns None if the file could not
        be retrieved. This expects PackageBase arguments.
        """
        for srcinfo in self.mdb.get_nth_field_many(self.SRCINFO_TABLE, args):
            if srcinfo:
                yield parse_srcinfo(srcinfo.split("\n"))
            else:
                yield None

    def get_pkginfo(self, pkgbases_and_pkgnames):
        """
        Retrieve package information.

        pkgbases_and_pkgnames: An iterator over package base and package name pairs.
        """
        pkgbases, pkgnames = zip(*pkgbases_and_pkgnames)
        for pkgname, srcinfo in zip(pkgnames, self.get(pkgbases)):
            if srcinfo:
                yield get_pkginfo(srcinfo, pkgname)
            else:
                yield None


##################################### Main #####################################


def main(args=None):
    argparser = argparse.ArgumentParser(
        description="Retrieve AUR .SRCINFO files and display them as JSON."
    )
    argparser.add_argument("pkgname", nargs="+")
    pargs = argparser.parse_args(args)
    a = AurSrcinfo()
    json.dump(
        tuple(a.get_pkginfo(pargs.pkgname)), sys.stdout, indent="  ", sort_keys=True
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
