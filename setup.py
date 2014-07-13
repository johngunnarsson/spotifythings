from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='spotifythings',
    version='0.1.0', 
    description='A Spotify player controlled by RFID tags',
    long_description=long_description,
    url='http://spotifythings.com',
    author='John Gunnarsson',
    author_email='john.gunnarsson@gmail.com',
    license='GPL v2',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Multimedia :: Sound/Audio :: Players',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Programming Language :: Python :: 2.7',
        'Environment :: Web Environment',
        'Environment :: No Input/Output (Daemon)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux'
    ],
    keywords='spotify player rfid',
    packages=['spotifythings'],
    include_package_data = True,
    install_requires=[
        'lockfile==0.8',
        'python-daemon==1.5.5',
        'backports.ssl_match_hostname==3.4.0.2',
        'tornado==3.2.2',
        'pyalsaaudio==0.7',
        'pyspotify==1.11'],
    dependency_links = [
        'https://github.com/mopidy/pyspotify/archive/v1.x/develop.zip#egg=pyspotify-1.11'],
    entry_points={
        'console_scripts': [
            'spotifythings=spotifythings.spotifythings:main',
        ],
    },
)
