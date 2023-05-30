#!/usr/bin/env python3

import AUR.RPC as AUR
from sys import argv, exit


def main():
    maintainers = argv[1:]
    if not maintainers:
        print(
            "usage: {0} <maintainer> [<maintainer>, ...]\n\n    e.g. {0} Xyne".format(
                argv[0]
            )
        )
        exit(1)

    for maintainer in maintainers:
        print("{}'s packages, sorted by votes:".format(maintainer))
        aur = AUR.AUR()
        pkgs = list(aur.search(maintainer, by="maintainer"))
        if pkgs:
            pkgs.sort(key=lambda p: p["NumVotes"], reverse=True)
            left_width = max([len(p["Name"]) for p in pkgs])
            total_votes = sum(p["NumVotes"] for p in pkgs)
            totals = (("packages", len(pkgs)), ("total votes", total_votes))
            right_width = len(str(total_votes))

            for l, r in totals:
                left_width = max(left_width, len(l))
                right_width = max(right_width, len(str(r)))

            format_string = "    {{:<{:d}s}}\t{{:{:d}d}}".format(
                left_width, right_width
            )
            for pkg in pkgs:
                print(format_string.format(pkg["Name"], pkg["NumVotes"]))

            print("    " + "-" * left_width + "\t" + "-" * right_width)
            print(format_string.format("vote total", total_votes))
            print(format_string.format("package total", len(pkgs)))
        else:
            print("no packages found for {}".format(maintainer))
        print()


if __name__ == "__main__":
    main()
