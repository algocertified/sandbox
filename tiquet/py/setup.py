import setuptools


setuptools.setup(
    name="tiquet",
    version="0.0.1",
    author="tiquet.io Inc.",
    author_email='hardik@tiquet.io',
    packages=setuptools.find_packages(),
    description="Client libraries for interfacing with tiquet.io marketplace",
    install_requires=[
        "py-algorand-sdk",
        "pytest",
    ]
)
