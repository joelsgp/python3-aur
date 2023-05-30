#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2012-2015 Xyne
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# (version 2) as published by the Free Software Foundation.
#
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import gzip
import io
import logging
import os.path
import time
import urllib.request

import xdg.BaseDirectory

import AUR.common
import XCGF
import XCPF


################################## Constants ###################################

PKGLIST_PATH = "/packages.gz"
PKGLIST_URL = AUR.common.AUR_URL + PKGLIST_PATH


################################## Functions ###################################


def iterate_packages(path):
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            else:
                yield line.strip()


################################### Classes ####################################


class PkgList(object):
    """
    A class to retrieve and iterate over the list of AUR packages.
    """

    def __init__(self, path=None, ttl=AUR.common.DEFAULT_TTL, auto_refresh=False):
        """
        path:
          The local path under which to store the file.

        ttl:
          The time-to-live of the cached file. This is passed to XCGF.mirror as the
          cache_time option.

        auto_refresh:
          If True, automatically refresh the file when needed.
        """
        if not path:
            cache_dir = xdg.BaseDirectory.save_cache_path(AUR.common.XDG_NAME)
            path = os.path.join(cache_dir, os.path.basename(PKGLIST_PATH))
        self.path = path
        self.ttl = ttl
        self.auto_refresh = auto_refresh
        try:
            self.last_refresh = os.path.getmtime(self.path)
        except FileNotFoundError:
            self.last_refresh = None

    def refresh(self, force=False):
        if force:
            ttl = 0
        else:
            ttl = self.ttl
        with XCGF.Lockfile(self.path + ".lck", "PkgList") as p:
            XCGF.mirror(PKGLIST_URL, self.path, cache_time=ttl)
        self.last_refresh = time.time()

    def __iter__(self):
        if self.auto_refresh:
            # Refresh the list if it hasn't been refreshed yet
            if self.last_refresh is None or time.time() - self.last_refresh > (
                self.ttl if self.ttl > 0 else AUR.common.DEFAULT_TTL
            ):
                self.refresh()
        try:
            for p in iterate_packages(self.path):
                yield p
        except FileNotFoundError:
            if self.auto_refresh:
                logging.warning(
                    "previous PkgList auto-refresh failed, attempting to force a refresh"
                )
                self.refresh(force=True)
                try:
                    for p in iterate_packages(self.path):
                        yield p
                except FileNotFoundError:
                    pass
