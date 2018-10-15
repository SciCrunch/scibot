from setuptools import setup

with open('README.md', 'rt') as f:
    long_description = f.read()

setup(name='scibot',
      version='0.0.2',
      description='curation workflow automation and coordination',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/SciCrunch/scibot',
      author='Tom Gillespie',
      author_email='tgbugs@gmail.com',
      license='Apache 2.0',
      classifiers=[],
      keywords='rrid curation biocuration hypothesis hypothes.is web annotation',
      packages=['scibot'],
      install_requires=[
          'curio',
          'docopt',
          'flask',
          'gevent',
          'gunicorn',
          'hyputils',
          'lxml',
          'pyontutils',
      ],
      extras_require={},
      scripts=['bin/scibot-bookmarklet', 'bin/scibot-dashboard'],
      entry_points={
          'console_scripts': [
              'scibot-sync=scibot.sync:main'
          ],
      },
     )
