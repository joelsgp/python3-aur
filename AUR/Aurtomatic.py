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

import argparse
import errno
import getpass
import glob
import html.parser
import http.cookiejar
import logging
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import xdg.BaseDirectory

import AUR.common
import AUR.RPC
import XCGF


################################### Globals ####################################

INDEX_URL = AUR.common.AUR_URL + '/index.php'
LOGIN_URL = AUR.common.AUR_URL + '/login/'
# PKGSUBMIT_URL = AUR.common.AUR_URL + '/pkgsubmit.php'
PKGSUBMIT_URL = AUR.common.AUR_URL + '/submit/'
RPC_URL = AUR.common.AUR_URL + '/rpc.php'
ACTION_URL = AUR.common.AUR_URL + '/pkgbase'

TOKENSCRAPER_URL = AUR.common.AUR_URL + '/packages/python3-aur/'

PACKAGE_ACTIONS = (
  'unflag',
  'vote',
  'unvote',
  'notify',
  'unnotify',
)

FORM_ACTIONS = {
  'vote' : 'Vote',
  'unvote' : 'UnVote',
  'notify' : 'Notify',
  'unnotify' : 'UnNotify',
  'flag' : 'Flag',
  'unflag' : 'UnFlag',
  'disown' : 'Disown',
  'delete' : 'Delete',
  'adopt' : 'Adopt'
}

VALUE_ACTIONS = ('flag', 'comment', 'setkeywords')

DO_ACTIONS = ('adopt', 'disown', 'delete')

ACCOUNT_RESULTS_PER_PAGE = 50



################################## Functions ###################################

def get_default_cookiejar_path():
  '''
  Get the default path to the cookie jar.
  '''
  cache_dir = xdg.BaseDirectory.save_cache_path(AUR.common.XDG_NAME)
  return os.path.join(cache_dir, 'cookiejar.txt')



def load_login_file(fpath):
  '''
  Load login name and password from file.
  '''
  with open(fpath) as f:
    name = f.readline().rstrip('\n')
    passwd = f.readline().rstrip('\n')
  return name, passwd


@XCGF.deprecated
def prompt_comment(pkginfo):
  '''
  Deprecated comment prompt function.
  '''
  return prompt_input(pkginfo, 'Enter a comment.')



def prompt_input(pkginfo, prompt):
  '''
  Prompt the user for input.

  The EDITOR environment variable must be set.
  '''
  editor = os.getenv('EDITOR')
  if not editor:
    raise AurtomaticError('environment variable "EDITOR" is not set')
  if os.path.isdir('/dev/shm'):
    dpath = '/dev/shm'
  else:
    dpath = None
  with tempfile.TemporaryDirectory(dir=dpath) as d:
    fpath = os.path.join(d, pkginfo['Name'])
    marker = '###>'
    header = (
      'Package: {}'.format(pkginfo['Name']),
      'Webpage: {}/packages.php?ID={!s}'.format(AUR.common.AUR_URL, pkginfo['ID']),
      'Lines beginning with "{}" are ignored.'.format(marker),
      'If the rest of the file is empty, no comment will be submitted.',
      prompt
    )
    with open(fpath, 'w') as f:
      for line in header:
        f.write('{} {}\n'.format(marker, line))
    p = subprocess.Popen([editor, fpath])
    p.wait()
    comment = ''
    with open(fpath) as f:
      for line in f:
        if line.startswith(marker):
          continue
        comment += line
    return comment.strip()




################################### Classes ####################################

class AurtomaticError(Exception):
  '''
  Exceptions raised by AUR interactions and related functions.
  '''
  def __init__(self, msg):
    self.msg = msg

  def __str__(self):
    return self.msg



class TokenScraper(html.parser.HTMLParser):
  '''
  Scrape the hidden token field required for submitting forms.
  '''
  def __init__(self):
    super(self.__class__, self).__init__()
    self.parse_options = False
    self.token = None
    self.errors = list()
    self.parse_errorlist = False

  def handle_starttag(self, tag, attrs):
    # Get the hidden token value.
    if tag == 'input':
      a = dict(attrs)
      if a['type'] == 'hidden' and a['name'] == 'token' and a['value']:
        self.token = a['value']

    elif tag == 'ul':
      a = dict(attrs)
      try:
        if a['class'] == 'errorlist':
          self.parse_errorlist = True
      except KeyError:
        pass

  def handle_endtag(self, tag):
    if tag == 'ul' and self.parse_errorlist:
      self.parse_errorlist = False

  def handle_data(self, data):
    if self.parse_errorlist:
      self.errors.append(data)



class AccountScraper(html.parser.HTMLParser):
  '''
  Scrape account data from the account search results page.
  '''
  def __init__(self):
    super(self.__class__, self).__init__()
    self.headers = list()
    self.accounts = list()
    self.account = None
    self.in_h2 = False
    self.in_results = False
    self.header = False
    self.account_info = False

  def handle_starttag(self, tag, attrs):
    if tag == 'h2':
      self.in_h2 = True

    elif not self.in_results:
      return

    elif tag == 'th':
      self.header = True

    elif tag == 'td':
      self.account_info = True
      self.field_data = ''

    elif tag == 'tr':
      self.account = list()

  def handle_endtag(self, tag):
    if tag == 'h2':
      self.in_h2 = False

    elif not self.in_results:
      return

    elif tag == 'th':
      self.header = False

    elif tag == 'td':
      self.account_info = False
      data = self.field_data.strip()
      if not data:
        data = None
      self.account.append(data)

    elif tag == 'tr':
      if self.account:
        self.accounts.append(self.account)
        self.account = list()

    elif tag == 'table':
      self.in_results = False

  def handle_data(self, data):
    if self.in_h2 and data.strip() == 'Accounts':
      self.in_results = True
    elif not self.in_results:
      return
    elif self.header:
      data = data.strip()
      self.headers.append(data.strip())
    elif self.account_info:
      data = data.strip()
      if data == '&nbsp;':
        data = ''
      self.field_data += data



class Aurtomatic(object):
  '''
  A user object for interactive actions.
  '''

  def __init__(
    self,
    cookiejar_path=None,
    cookiejar=None,
    token=None
  ):
    '''
    cookiejar: a MozillaCookieJar object

    token: a user token for submitting form data
    '''

    if cookiejar_path is None:
      cookiejar_path = get_default_cookiejar_path()
    self.cookiejar_path = cookiejar_path

    if cookiejar is None:
      self.cookiejar = http.cookiejar.MozillaCookieJar()
      self.load_cookies()
    else:
      self.cookiejar = cookiejar

    # TODO
    # Find way to use this with URL opener. (urlopen accepts a capath arg)
    # CA_PATH = '/etc/ssl/certs'
    self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookiejar))
    self.token = token

#     self.rpc = AUR.RPC.AUR(ttl=0, clean=False)
    self.rpc = AUR.RPC.AurRpc()



  def get_info(self, pkgname):
    '''
    Get package information from the RPC interface.
    '''
    for pkg in self.rpc.info(pkgname):
      return pkg



  def load_token(self):
    '''
    Attempt to load the hidden token. If the token is empty after this operation
    then the user is not currently logged in, so it doubles as a login check.
    '''
    parser = TokenScraper()
    with self.opener.open(TOKENSCRAPER_URL) as f:
      parser.feed(f.read().decode())
    if parser.token:
      self.token = parser.token
      return True
    else:
      return False



  def login(self, user=None, passwd=None, login_file=None, remember_me=True):
    '''
    Log in to the AUR.
    '''
    if login_file is not None:
      user, passwd = load_login_file(login_file)

    if user is None or passwd is None:
      logging.info("logging in to the AUR")

    if user is None:
      user = input('Username: ')

    if passwd is None:
      passwd = getpass.getpass()

    data = [
      ('user', user),
      ('passwd', passwd)
    ]

    if remember_me:
      data.append(('remember_me', '1'))

    data = urllib.parse.urlencode(data).encode('UTF-8')

    with self.opener.open(LOGIN_URL, data) as f:
      pass



  # python3-AUR could be used to cache the data, but sometimes the data must be
  # fresh, such as when confirming the upload.
  def submit_package_form(
    self, pkginfo, action,
    confirm=False, merge_into=None, value=None, comment=None, comment_id=None
  ):
    '''
    Submit a form to the AUR.
    '''

    if comment is not None:
      XCGF.warn_deprecated('keyword argument "comment" in submit_package_form is deprecated in favor of "value"')
      value = comment

    ID = pkginfo['ID']
    url = ACTION_URL + '/{}/'.format(pkginfo['PackageBase'])

    #Perform one of the link-based package actions.
    if action in PACKAGE_ACTIONS:
      url += action
      data = (
        ('token', self.token),
      )

    elif action in FORM_ACTIONS:
      if action in DO_ACTIONS or action == 'flag':
        ID = pkginfo['PackageBaseID']
      a = FORM_ACTIONS[action]
      data = [
        ('IDs[{!s}]'.format(ID), '1'),
        ('ID', ID),
        ('token', self.token),
        ('do_{}'.format(a), a)
      ]
      if confirm:
        data.append(('confirm', '1'))
      if merge_into:
        data.append(('merge_Into', merge_into))
      if action == 'flag':
        if not value:
          value = prompt_input(pkginfo, 'Why you are flagging this package?')
        data.append(('comments', value))

    elif action == 'comment':
      if not value:
        value = prompt_input(pkginfo, 'Enter a comment.')
      if value:
        data = (
          ('action', 'do_AddComment'),
          ('ID', ID),
          ('token', self.token),
          ('comment', value)
        )
      else:
        raise AurtomaticError("no comment submitted")

    elif action == 'setkeywords':
      if value is None:
        value = prompt_input(pkginfo, 'Enter keywords (or nothing to clear them).')
      if value:
        if not isinstance(value, str):
          try:
            value = ' '.join(value)
          except TypeError:
            value = str(value)
      else:
        value = ''
      data = (
        ('action', 'do_SetKeywords'),
        ('token', self.token),
        ('keywords', value)
      )

    elif action == 'do_DeleteComment':
      if comment_id:
        data = (
          ('action', 'do_DeleteComment'),
          ('comment_id', comment_id),
          ('token', self.token),
          ('submit', '1')
        )
      else:
        raise AurtomaticError('no comment ID submitted for do_DeleteComment')

    else:
      raise AurtomaticError('unrecognized form action: {}'.format(action))

    logging.debug('POSTing data to {}: {}'.format(url, data))
    data = urllib.parse.urlencode(data).encode('UTF-8')
    with self.opener.open(url, data) as f:
      pass



  def search_accounts(
    self,
    username=None,
    typ=None,
    suspended=False,
    email=None,
    realname=None,
    ircname=None,
    sortby=None,
    max_results=ACCOUNT_RESULTS_PER_PAGE,
  ):
    '''
    Submit a search form and scrape the results.

    Valid types:
      u: normal user
      t: trusted user
      d: developer
      td: trusted user & developer

    Valid sortby options:
      u: user name
      t: account type
      r: real name
      i: IRC name
    '''

    if suspended:
      suspended = 1

    if not sortby:
      sortby = 'u'

    url = AUR.common.AUR_URL + '/accounts/'
    data = {
      'Action': 'SearchAccounts',
      'O' : -ACCOUNT_RESULTS_PER_PAGE,
    }
    # 0 : 50
    for field, value in (
      ('U', username),
      ('T', typ),
      ('S', suspended),
      ('E', email),
      ('R', realname),
      ('I', ircname),
      ('SB', sortby)
    ):
      if value:
        data[field] = value

    headers = None
    accounts = list()

    while True:
      data['O'] += ACCOUNT_RESULTS_PER_PAGE
      encdata = urllib.parse.urlencode(data).encode('UTF-8')
      parser = AccountScraper()
      with self.opener.open(url, encdata) as f:
        parser.feed(f.read().decode())
      if headers is None:
        headers = parser.headers.copy()
      if parser.accounts:
        accounts.extend(parser.accounts)
        if max_results > 0 and len(accounts) > max_results:
          accounts = accounts[:max_results]
          break
        elif len(parser.accounts) < ACCOUNT_RESULTS_PER_PAGE:
          break
      else:
        break

    return headers, accounts


  @XCGF.deprecated
  def upload_pkg(self, fpath, confirm=True):
    '''
    Upload a package to the AUR. This is no longer supported.
    '''
    raise AurtomaticError('Package uploads are no longer supported since AUR 4.0 due to the move to Git repos via SSH. Handling that is better left to user scripts.')



  def save_cookies(self, path=None):
    '''
    Save cookie jar.
    '''
    if path is None:
      path = self.cookiejar_path
    if path is None:
      raise AurtomaticError('save_cookies: no cookiejar path given')
    # For Curl compatibility (not sure which one fails to comply with the standard.
    for cookie in self.cookiejar:
      if not cookie.expires:
        cookie.expires = 0
    self.cookiejar.save(path, ignore_discard=True, ignore_expires=True)


  def load_cookies(self, path=None):
    '''
    Load cookie jar.
    '''
    if path is None:
      path = self.cookiejar_path
    if path is None:
      raise AurtomaticError('load_cookies: no cookiejar path given')
    try:
      # For Curl compatibility (not sure which one fails to comply with the standard.
      self.cookiejar.load(path, ignore_discard=True, ignore_expires=True)
      for cookie in self.cookiejar:
        if not cookie.expires:
          cookie.expires = None
    except http.cookiejar.LoadError:
      pass
    except IOError as e:
      if e.errno != errno.ENOENT:
        raise e



  def remove_cookies(self, path=None):
    '''
    Save cookie jar.
    '''
    if path is None:
      path = self.cookiejar_path
    if path is None:
      raise AurtomaticError('remove_cookies: no cookiejar path given')
    else:
      try:
        os.unlink(self.cookiejar_path)
      except FileNotFoundError:
        pass




  def initialize(self, user=None, passwd=None, login_file=None, cookiejar_path=None):
    '''
    Reload token and log in if necessary.
    '''
    self.load_cookies(cookiejar_path)
    if not self.load_token():
      self.login(user=user, passwd=passwd, login_file=login_file)
      if not self.load_token():
        raise AurtomaticError('login appears to have failed\n')
      elif cookiejar_path:
        self.save_cookies(cookiejar_path)



class CookieWrapper(object):
  ACTIONS = ('ask', 'keep', 'remove')

  def __init__(self, path=None, action='ask', login_file=None):
    self.action = action
    self.login_file=login_file
    self.aurtomatic = Aurtomatic(cookiejar_path=path)


  def __enter__(self):
    '''
    Cookie context manager.
    '''
    self.aurtomatic.initialize(login_file=self.login_file)
    return self.aurtomatic



  def __exit__(self, typ, value, traceback):
    '''
    Cookie context manager.
    '''
    action = self.action

    if action not in ('remove', 'keep'):
      cookie_prompts = (
        'Keep cookie jar? [y/n]',
        'Invalid response. Would you like to keep the cookie jar? [y/n]',
        'Please enter "y" or "n". Would you like to keep the cookie jar? [y/n]',
        'Wtf is wrong with you? Just press "y" or "n". I don\'t even care about the case.',
        'I am not going to ask you again. Do you want to keep the cookie jar or what?'
      )
      ans = 'n'
      for prompt in cookie_prompts:
        ans = input(prompt + ' ').lower()
        if ans in 'yn':
          break
      else:
        print('Ok, that\'s it, @#$^ your cookies! Have fun logging in again!')
        ans = 'n'
      if ans == 'n':
        action = 'remove'
      else:
        action = 'keep'

    if action == 'remove':
      self.aurtomatic.remove_cookies()
    else:
      self.aurtomatic.save_cookies()



##################################### Main #####################################

def parse_args(args=None):
  parser = argparse.ArgumentParser(description='Upload packages to the AUR.')
  parser.add_argument(
    'paths', metavar='<path>', nargs='*',
    help='Arguments are either paths to source archives created with "makepkg --source", or to directories containing such source archives. Simple pattern matching is used to search for "*.src.*". If no paths are given then the current directory is searched.'
  )
  parser.add_argument(
    '-c', '--cookiejar', metavar='<path>',
    help='Specify the path of the cookie jar. The file follows the Netscape format.'
  )
  parser.add_argument(
    '--comment', action='store_true',
    help='Prompt for a comment for each uploaded package. This option requires that the EDITOR environment variable be set.'
  )
  parser.add_argument(
    '-k', '--keep-cookiejar', dest='keep', action='store_true',
    help='Keep the cookie jar.'
  )
  parser.add_argument(
    '-l', '--login', metavar='<path>',
    help='Read name and password from a file. The first line should contain the name and the second the password.'
  )
  parser.add_argument(
    '-m', '--message', metavar='<message>',
    help='Post a message as a comment. The same message will be used for all packages. Use the --comment option to set per-package comments when uploading multiple packages..'
  )
  parser.add_argument(
    '-n', '--notify', action='store_true',
    help='Receive notifications for each uploaded package.'
  )
  parser.add_argument(
    '-r', '--remove-cookiejar', dest='remove', action='store_true',
    help='Remove the cookie jar.'
  )
  parser.add_argument(
    '-v', '--vote', action='store_true',
    help='Vote for each uploaded package.'
  )
  return parser.parse_args()








def main(args=None):
  pargs = parse_args(args)

  # Search current directory for source archives if none were specified. This
  # allows e.g. "makepkg --source; aurploader" without explicit arguments.
  if not pargs.paths:
    pkgs = glob.glob('*.src.*')
  else:
    pkgs = []
    for path in pargs.paths:
      if os.path.isdir(path):
        ps = glob.glob(os.path.join(path, '*.src.*'))
        if ps:
          pkgs.extend(ps)
        else:
          raise AurtomaticError('no source package found in directory ({})'.format(path))
      else:
        pkgs.append(path)

  if pargs.remove:
    action = 'remove'
  elif pargs.keep:
    action = 'keep'
  else:
    action = 'ask'

  with CookieWrapper(path=pargs.cookiejar, action=action, login_file=pargs.login) as aurtomatic:
    for pkg in pkgs:
      print('Uploading {}'.format(pkg))
      pkginfo = aurtomatic.upload_pkg(
        pkg,
        confirm=True,
        ignore_missing_aurinfo=pargs.ignore_missing_aurinfo,
      )
      if pkginfo:
        if pargs.vote:
          aurtomatic.submit_package_form(pkginfo, 'vote')
        if pargs.notify:
          aurtomatic.submit_package_form(pkginfo, 'notify')
        comment = None
        if pargs.comment:
          comment = prompt_comment(pkginfo)
        elif pargs.message:
          comment = pargs.message
        if comment:
          aurtomatic.submit_package_form(pkginfo, 'comment', comment=comment)
      print()



def run_main(args=None):
  '''
  Run main() with exception handling.
  '''
  try:
    main(args)
  except (KeyboardInterrupt, BrokenPipeError):
    pass
  except AurtomaticError as e:
    sys.exit('error: {}\n'.format(e.msg))
  except urllib.error.URLError as e:
    sys.exit('URLError: {}\n'.format(e))


if __name__ == '__main__':
  run_main()
