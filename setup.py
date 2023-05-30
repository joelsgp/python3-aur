#!/usr/bin/env python3

from distutils.core import setup
import time

setup(
  name='AUR',
  version=time.strftime('%Y.%m.%d.%H.%M.%S', time.gmtime(1637376062)),
  description='AUR-related modules and helper utilities (aurploader, aurquery, aurtomatic).',
  author='Xyne',
  author_email='gro xunilhcra enyx, backwards',
  url='http://xyne.dev/projects/python3-aur',
  packages=['AUR'],
  scripts=['aurpkglist', 'aurploader', 'aurquery', 'aurtomatic', 'aurtus']
)
