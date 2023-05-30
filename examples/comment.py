#!/usr/bin/env python3
from AUR.Aurtomatic import Aurtomatic, AurtomaticError, prompt_comment
from sys import argv, stderr, exit

# This is a very simple example of how to post comments to the AUR. This is the
# base of what later became aurtomatic.

if argv[1:]:
    aurt = Aurtomatic()
    aurt.initialize()

    for pkgname in argv[1:]:
        pkginfo = aurt.get_info(pkgname)
        print("posting comment for {}".format(pkginfo["Name"]))
        try:
            comment = prompt_comment(pkginfo)
        except AurtomaticError as e:
            stderr.write(str(e))
            exit(1)
        if comment:
            aurt.submit_package_form(pkginfo, "comment", comment=comment)
