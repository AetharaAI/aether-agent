"""
Skill Loader

Loads skills from YAML manifests and Python modules.
"""

import os
import yaml
import importlib.util
from pathlib import Path
from typing import List
import logging

from .registry import SkillRegistry, Skill

logger = logging.getLogger(__name__)


def load_skills_from_directory(directory: str, registry: SkillRegistry) -> int:
    """
    Load all skills from a directory.

    Looks for:
    - Python files with Skill subclasses
    - YAML manifests with skill definitions

    Args:
        directory: Path to skills directory
        registry: SkillRegistry to register skills in

    Returns:
        Number of skills loaded
    """
    skills_path = Path(directory)
    if not skills_path.exists():
        logger.warning(f"Skills directory not found: {directory}")
        return 0

    loaded = 0

    # Load Python modules
    for py_file in skills_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        try:
            loaded += _load_python_skill(py_file, registry)
        except Exception as e:
            logger.error(f"Failed to load skill from {py_file}: {e}")

    # Load YAML manifests
    for yaml_file in skills_path.glob("*.yaml"):
        try:
            loaded += _load_yaml_skill(yaml_file, registry)
        except Exception as e:
            logger.error(f"Failed to load skill from {yaml_file}: {e}")

    logger.info(f"Loaded {loaded} skills from {directory}")
    return loaded


def _load_python_skill(py_file: Path, registry: SkillRegistry) -> int:
    """Load skill from Python module"""
    spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
    if not spec or not spec.loader:
        return 0

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find Skill subclasses
    loaded = 0
    for name in dir(module):
        obj = getattr(module, name)
        if (isinstance(obj, type) and
            issubclass(obj, Skill) and
            obj is not Skill and
            hasattr(obj, 'metadata')):
            try:
                skill_instance = obj()
                registry.register(skill_instance)
                loaded += 1
            except Exception as e:
                logger.error(f"Failed to instantiate skill {name}: {e}")

    return loaded


def _load_yaml_skill(yaml_file: Path, registry: SkillRegistry) -> int:
    """Load skill from YAML manifest (for simple prompt-based skills)"""
    # YAML skills are for future expansion
    # Currently we use Python classes for full control
    return 0
