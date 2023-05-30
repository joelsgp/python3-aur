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

################################## Constants ###################################

XDG_NAME = "AUR"
AUR_HOST = "aur.archlinux.org"
AUR_URL = "https://" + AUR_HOST
# AUR_URL = 'https://aur-dev.archlinux.org'
AUR_GIT_URL_FORMAT = AUR_URL + "/{}.git"
AUR_SSH_GIT_URL = "ssh+git://aur@" + AUR_HOST

DEFAULT_TTL = 15 * 60
