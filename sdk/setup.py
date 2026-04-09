from setuptools import setup, find_packages

setup(
    name="botmarket-sdk",
    version="0.1.0",
    description="Python SDK for the BOTmarket agent compute exchange",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://botmarket.dev",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],  # stdlib only; install PyNaCl for Ed25519 auth
    extras_require={
        "ed25519": ["PyNaCl>=1.5"],
    },
    entry_points={
        "console_scripts": [
            "botmarket-sell=botmarket_sdk.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Libraries",
    ],
)
