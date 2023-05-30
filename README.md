# python3-aur

This repo is an **unofficial mirror** of Xyne's Python library for interacting with the AUR (Arch User Repository)

- Upstream URL: https://xyne.dev/projects/python3-aur/
- AUR install URL: https://aur.archlinux.org/packages/python3-aur

_The following text was taken from the upstream html page and converted to markdown_

## About

This package contains Python 3 modules for interacting with the AUR along with some tools that use them.

Example scripts are provided in the scripts directory.

See [paconky.py](https://xyne.dev/scripts/conky/) for an example of how this can be used with pyalpm.
## Command-Line Utilities

The following are installed with the package. See help messages below for more information.

**aurtomatic**

Aurtomatic lets you do the following from the command-line for multiple packages:

* comment
* vote
* unvote
* notify
* unnotify
* flag
* unflag

Show support for the AUR packages that you use by running

`aurtomatic -i -a vote`

### aurquery

Aurquery is a caching wrapper around the [AUR’s RPC interface](https://aur.archlinux.org/rpc.php) for querying package information from the command line. Information is returned in a format similar to pacman’s “-Si” output.

### aurploader

** Note: uploading is deprecated since the switch to Git repos. **

Aurploader is a command-line utility for uploading packages to the AUR. You can do the following when uploading a package:

* select a category (with automatic detection for existing packages)
* post a comment
* request notifications
* vote

#### Usage

`aurcomment <pkgname> [<pkgname>...]`

### aurpkglist

Print the list of AUR packages. The script also maintains a locally cached list.

## Modules

### AUR.RPC

Retrieve and cache data from the AUR’s [RPC interface](https://aur.archlinux.org/rpc.php). Results are cached in an SQLite3 database and are refreshed after a configurable interval.

This was the original AUR module before Aurploader was included.

### AUR.Aurtomatic

Interact with the AUR. The following actions are supported:

* log in
* upload packages
* post comments
* all package actions (vote, unvote, notify, unnotify, change tags, etc.)

This module was originally part of [aurploader](https://xyne.dev/projects/aurploader/).

### AUR.PkgList

Retrieve a full list of AUR packages. The module provides a class for mirroring the remote file and iterating over the package names in the list. The gzipped list is available online here.

### AUR.SRCINFO

Parse information in a **.SRCINFO** file.

## Complementary Modules

* [pyalpm](https://projects.archlinux.org/users/remy/pyalpm.git/)
* [XCPF](https://xyne.dev/projects/python3-xcpf/)
* [Reflector](https://xyne.dev/projects/reflector/)

## Aurquery Help Message

```$ aurquery -h

usage: aurquery [-h] [-i] [-s] [--by {name,name-desc,maintainer}] [--debug]
                [--log <path>] [--ttl <minutes>] [--full-info] [--intersect]
                <arg> [<arg> ...]

Query the AUR RPC interface.

positional arguments:
  <arg>

options:
  -h, --help            show this help message and exit
  -i, --info            Query package information.
  -s, --search          Search the AUR.
  --by {name,name-desc,maintainer}
                        By which fields to search. Default: name-desc
  --debug               Enable debugging.
  --log <path>          Log debugging information to <path>.
  --ttl <minutes>       Time-to-live of cached data (default: 15)
  --full-info           Return full information for searches and msearches.
  --intersect           When searching for packages, only return results that
                        match all search terms.

For maintainer searches, use an empty string ('') as an argument to search for
orphans.
```

## Aurtomatic Help Message Output

```$ aurtomatic -h

usage: aurtomatic [-h]
                  [-a {adopt,comment,delete,disown,flag,notify,setkeywords,unflag,unnotify,unvote,vote} [{adopt,comment,delete,disown,flag,notify,setkeywords,unflag,unnotify,unvote,vote} ...]]
                  [--comment COMMENT] [--comment-from-file <path>]
                  [--keywords [KEYWORD ...]] [-i] [-q] [-c <path>]
                  [-j {ask,keep,remove}] [-l <path>] [--confirm]
                  [--merge-into MERGE_INTO]
                  [<pkgname> ...]

Post comments to the AUR.

positional arguments:
  <pkgname>

options:
  -h, --help            show this help message and exit
  -a {adopt,comment,delete,disown,flag,notify,setkeywords,unflag,unnotify,unvote,vote} [{adopt,comment,delete,disown,flag,notify,setkeywords,unflag,unnotify,unvote,vote} ...], --action {adopt,comment,delete,disown,flag,notify,setkeywords,unflag,unnotify,unvote,vote} [{adopt,comment,delete,disown,flag,notify,setkeywords,unflag,unnotify,unvote,vote} ...]
                        Action(s) to perform for each specified package.
  --comment COMMENT     Post a comment without the interactive prompt.
  --comment-from-file <path>
                        Load a comment from a path without the interactive
                        prompt.
  --keywords [KEYWORD ...]
                        Set keywords without the interactive prompt.
  -i, --installed       Perform action for all installed AUR packages. Use
                        this to vote for the packages that you use and show
                        support.
  -q, --quiet           Suppress output.

cookie-management arguments:
  -c <path>, --cookiejar <path>
                        Specify the path of the cookie jar. The file follows
                        the Netscape format.
  -j {ask,keep,remove}, --jar {ask,keep,remove}
                        What to do with the cookiejar. Default: ask.
  -l <path>, --login <path>
                        Read name and password from a file. The first line
                        should contain the name and the second the password.

deletion arguments:
  --confirm             Confirm deletion and other actions requiring
                        additional confirmation.
  --merge-into MERGE_INTO
                        Merge target when deleting package.
```
## Aurpkglist Help Message Output

```$ aurpkglist -h

usage: aurpkglist [-h] [-f] [-t TTL] [-p PATH] [-q]

Retrieve and print the full list of AUR packages.

options:
  -h, --help            show this help message and exit
  -f, --force           Force a refresh of the local file.
  -t TTL, --ttl TTL, --time TTL
                        The time, in seconds, to cache the local file, counted
                        from the last modification. Default: 900
  -p PATH, --path PATH  Set the local file path.
  -q, --quiet           Refresh the local file without printing the list of
                        packages.
```
## AurTUs Help Message Output

```$ aurtus -h

usage: aurtus [-h] [-c <path>] [-j {ask,keep,remove}] [-l <path>]

Retrieve the current list of trusted users (TUs) from the AUR.

options:
  -h, --help            show this help message and exit
  -c <path>, --cookiejar <path>
                        Specify the path of the cookie jar. The file follows
                        the Netscape format.
  -j {ask,keep,remove}, --jar {ask,keep,remove}
                        What to do with the cookiejar. Default: ask.
  -l <path>, --login <path>
                        Read name and password from a file. The first line
                        should contain the name and the second the password.
```
