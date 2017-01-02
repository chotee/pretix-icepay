#!/usr/bin/env python

from setuptools import setup

setup(
    name='pretix-icepay',
    version='0.0.1',
    description='Pretix extension for the Icepay payment provider.',
    author='chotee',
    author_email='chotee@openended.eu',
    dependency_links=[
        'git+https://github.com/edelooff/icepay-python.git#egg=icepay-python',
    ],
    packages=['pretix_icepay'],
    install_requires=['icepay_python'],
    url='https://github.com/chotee/pretix-icepay',
    entry_points={
        'pretix.plugin': 'pretix_icepay = pretix_icepay:PretixPluginMeta'}
)
