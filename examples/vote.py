#!/usr/bin/env python

from AUR.Aurtomatic import Aurtomatic
from sys import argv

if argv[1:]:
    aurt = Aurtomatic()
    aurt.initialize()

    for pkgname in argv[1:]:
        pkginfo = aurt.get_info(pkgname)
        print("voting for {}".format(pkginfo["Name"]))
        aurt.do_package_action(pkginfo, "vote")
