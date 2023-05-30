#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2016-2021 Xyne
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

import urllib.error

import AUR.SRCINFO
import XCPF.ArchPkg


# ---------------------------------- PkgSet ---------------------------------- #

class AurPkgSet(XCPF.ArchPkg.PkgSet):

    def __init__(self, pkgs=None):
        accessors = {
            'name': lambda x: x['Name'],
            'version': lambda x: x['Version']
        }
        super(self.__class__, self).__init__(accessors, pkgs=pkgs)


# ---------------------------- Buildable Packages ---------------------------- #

class AurBuildablePkgFactory(XCPF.ArchPkg.BuildablePkgFactory):
    '''
    Wrapper class to convert AUR packages to AurBuildablePkgs.

    arch: Target architecture.
    asi: AUR.SRCINFO.AurSrcinfo instance.
    '''

    def __init__(self, arch, *args, asi=None, **kwargs):
        self.arch = arch
        if asi is None:
            asi = AUR.SRCINFO.AurSrcinfo(*args, **kwargs)
        self.asi = asi

    def pkg(self, pkg):
        return AurBuildablePkg(self.arch, pkg, asi=self.asi)


class AurBuildablePkg(XCPF.ArchPkg.BuildablePkg):
    # TODO
    # Remove the .SRCINFO retrieval once the RPC interface catches up.

    def __init__(self, arch, pkg, asi=None):
        super(self.__class__, self).__init__(arch)
        self.pkg = pkg
        self.srcinfo = None
        if asi is None:
            asi = AUR.SRCINFO.AurSrcinfo()
        self.asi = asi

    # Lazy retrieval.
    def get_srcinfo(self):
        if self.srcinfo is None:
            try:
                pkgbases_and_pkgnames = ((self.pkg['PackageBase'], self.pkg['Name']),)
                for si in self.asi.get_pkginfo(pkgbases_and_pkgnames):
                    self.srcinfo = si
                    break
            except urllib.error.HTTPError as e:
                raise XCPF.ArchPkg.BuildablePkgError(
                    'failed to retrieve .SRCINFO for {}'.format(self.pkg.name),
                    error=e
                )
        return self.srcinfo

    def buildable(self):
        return True

    def maintainers(self):
        m = self.pkg['Maintainer']
        if m:
            yield m

    def pkgname(self):
        return self.pkg.get('Name')

    def version(self):
        return self.pkg.get('Version')

    def pkgbase(self):
        return self.pkg.get('PackageBase')

    def repo(self):
        return 'AUR'

    def last_modified(self):
        return self.pkg.get('LastModified')

    def last_packager(self):
        return self.pkg.get('LastPackager')

    def with_arch_deps(self, field):
        # for SRCINFO
        field = field.lower()
        srcinfo = self.get_srcinfo()
        if self.arch == 'any':
            fields = [field]
        else:
            fields = [field, '{}_{}'.format(field, self.arch)]

        for f in fields:
            try:
                #         for d in self.pkg[f]:
                for d in srcinfo[f]:
                    yield d
            except KeyError:
                continue

    def deps(self):
        return self.with_arch_deps('Depends')

    def makedeps(self):
        return self.with_arch_deps('MakeDepends')

    def checkdeps(self):
        return self.with_arch_deps('CheckDepends')
