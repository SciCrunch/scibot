import re
from setuptools import setup


def find_version(filename):
    _version_re = re.compile(r"__version__ = ['\"](.*)['\"]")
    last = None  # match python semantics
    for line in open(filename):
        version_match = _version_re.match(line)
        if version_match:
            return version_match.group(1)

    return last


__version__ = find_version('scibot/__init__.py')

with open('README.md', 'rt') as f:
    long_description = f.read()

tests_require = ['pytest', 'pytest-runner']
setup(name='scibot',
      version=__version__,
      description='curation workflow automation and coordination',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/SciCrunch/scibot',
      author='Tom Gillespie',
      author_email='tgbugs@gmail.com',
      license='Apache 2.0',
      classifiers=[
          'Development Status :: 4 - Beta',
          #'License :: OSI Approved :: Apache 2',  # pypi doesn't have v2
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          #'Programming Language :: Python :: 3.10',
          #'Programming Language :: Python :: 3.11',
          'Programming Language :: Python :: Implementation :: CPython',
          #'Programming Language :: Python :: Implementation :: PyPy',
          'Operating System :: POSIX :: Linux',
      ],
      keywords='rrid curation biocuration hypothesis hypothes.is web annotation',
      packages=['scibot'],
      tests_require=tests_require,
      install_requires=[
          'beautifulsoup4',
          'curio>=1.0',
          'docopt',
          'flask',
          'gevent',
          'gunicorn',
          'hyputils[memex]>=0.0.4',
          "ipython; python_version < '3.7'",
          'lxml',
          'pyontutils>=0.1.4',
      ],
      extras_require={'dev':['pyontutils',],
                      'test': tests_require},
      scripts=['bin/scibot-bookmarklet', 'bin/scibot-dashboard'],
      entry_points={
          'console_scripts': [
              'scibot-sync=scibot.sync:main'
          ],
      },
     )
