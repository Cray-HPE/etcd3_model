from setuptools import setup, find_packages

with open('etcd3_model/version.py') as vers_file:
    exec(vers_file.read())  # Get VERSION from version.py

setup(
    name='etcd3_model',
    version=VERSION,
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    install_requires=[
        "etcd3",
    ]
)
