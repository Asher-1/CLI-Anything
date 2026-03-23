#!/usr/bin/env python3
"""
Setup script for cli-anything-acloudviewer

Install (dev mode):
    pip install -e .

Build:
    python -m build

Publish:
    twine upload dist/*
"""

from pathlib import Path
from setuptools import setup, find_namespace_packages

ROOT = Path(__file__).parent
README = ROOT / "cli_anything/acloudviewer/README.md"

long_description = README.read_text(encoding="utf-8") if README.exists() else ""

setup(
    name="cli-anything-acloudviewer",
    version="3.0.0",
    description="CLI harness for ACloudViewer — 3D point cloud and mesh processing via binary CLI and JSON-RPC, with Colmap reconstruction and SIBR pipelines",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="ACloudViewer Contributors",
    author_email="admin@cloudViewer.org",
    url="https://github.com/Asher-1/CLI-Anything",

    project_urls={
        "Source": "https://github.com/Asher-1/CLI-Anything",
        "Tracker": "https://github.com/Asher-1/CLI-Anything/issues",
        "ACloudViewer": "https://github.com/Asher-1/ACloudViewer",
    },

    license="MIT",

    packages=find_namespace_packages(include=("cli_anything.*",)),

    python_requires=">=3.10",

    install_requires=[
        "click>=8.1",
        "websockets>=11.0",
        "prompt-toolkit>=3.0",
    ],

    extras_require={
        "mcp": ["mcp>=1.0"],
        "dev": [
            "pytest>=7",
            "pytest-cov>=4",
        ],
    },

    entry_points={
        "console_scripts": [
            "cli-anything-acloudviewer=cli_anything.acloudviewer.acloudviewer_cli:main",
            "cli-anything-acloudviewer-mcp=cli_anything.acloudviewer.mcp_server:main",
        ],
    },
    package_data={
        "cli_anything.acloudviewer": ["skills/*.md"],
    },
    include_package_data=True,
    zip_safe=False,

    keywords=[
        "cli",
        "acloudviewer",
        "point-cloud",
        "mesh",
        "3d",
        "colmap",
        "reconstruction",
        "automation",
    ],

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",

        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
