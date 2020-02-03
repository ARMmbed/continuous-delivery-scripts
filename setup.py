"""Package definition for PyPI."""
from setuptools import setup, find_packages
import os

PACKAGE_NAME = 'mbed-tools-ci-scripts'
SOURCE_DIR = 'mbed_tools_ci_scripts'
__version__ = None

repository_dir = os.path.dirname(__file__)

# Read package version, this will set the variable `__version__` to the current version.
with open(os.path.join(repository_dir, SOURCE_DIR, '_version.py')) as fh:
    exec(fh.read())

setup(
    name=PACKAGE_NAME,
    version=__version__,
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            f"assert-news={SOURCE_DIR}.assert_news:main",
            f"generate-news={SOURCE_DIR}.generate_news:main",
            f"generate-docs={SOURCE_DIR}.generate_docs:main",
            f"tag-and-release={SOURCE_DIR}.tag_and_release:main",
            f"get-config={SOURCE_DIR}.get_config:main",
        ],
    },
    install_requires=[
        'gitpython',
        'towncrier',
        'pyautoversion',
        'pdoc3',
        'toml',
        'python-dotenv',
        'twine',
    ],
)
