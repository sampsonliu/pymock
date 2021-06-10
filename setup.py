from setuptools import setup

setup(
    name='pymock',
    version='1.0.0',
    description='python mock and tunnel server',
    author='triplezee',
    packages=['pymock'],
    package_data={
        'pymock': ['res/*'],
    },

    entry_points={
        'console_scripts': [
            'pymock=pymock.main:main'
        ]
    },

    install_requires=[
        'tornado'
    ]
)
