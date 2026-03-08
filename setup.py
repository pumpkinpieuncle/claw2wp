from setuptools import setup, find_packages

setup(
    name='claw2wp',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'requests',
        'python-frontmatter',
        'markdown',
        'mammoth',
        'beautifulsoup4',
        'html2text',
        'mistletoe',
    ],
    entry_points={
        'console_scripts': [
            'claw2wp=claw2wp.cli:main',
        ],
    },
    author='Claw2WP',
    description='A CLI tool to publish Markdown and Docx files to WordPress, specially supporting WooCommerce products.',
)
