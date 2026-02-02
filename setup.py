"""
Setup script for Aether Agent package
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "docs" / "README.md").read_text()

setup(
    name="aether-agent",
    version="1.0.0",
    author="AetherPro Technologies",
    author_email="cory@aetherpro.tech",
    description="Semi-autonomous AI assistant with Redis memory and Fleet orchestration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AetharaAI/aether-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "redis[hiredis]>=5.0.0",
        "aiohttp>=3.9.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "tenacity>=8.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "mypy>=1.5.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "aether=aether.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "aether": ["*.md", "config/*.yaml", "workspace/skills/*.md"],
    },
)
