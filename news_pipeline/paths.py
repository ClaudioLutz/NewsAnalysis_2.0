"""
Centralized path resolution utilities for robust file access.

This module provides utilities to resolve file paths relative to the project root,
making the application work regardless of the current working directory.
Solves the common issue where Task Scheduler runs processes from C:\Windows\System32.
"""

from pathlib import Path
import os


def project_root() -> Path:
    """
    Get the project root directory (NewsAnalysis_2.0 folder).
    
    This function locates the project root by looking for characteristic files
    like setup.py, requirements.txt, or the news_pipeline directory.
    
    Returns:
        Path: Absolute path to the project root
        
    Raises:
        RuntimeError: If project root cannot be determined
    """
    # Start from this file's location and work upward
    current = Path(__file__).resolve().parent  # news_pipeline directory
    project_dir = current.parent  # NewsAnalysis_2.0 directory
    
    # Verify we found the correct project root by checking for characteristic files
    markers = [
        "setup.py",
        "requirements.txt", 
        "news_analyzer.py",
        "config/feeds.yaml",
        "news_pipeline/__init__.py"
    ]
    
    for marker in markers:
        if (project_dir / marker).exists():
            return project_dir
    
    # If we can't find markers, raise an error with helpful information
    raise RuntimeError(
        f"Cannot determine project root. Current path: {current}\n"
        f"Expected project root: {project_dir}\n"
        f"Looking for markers: {markers}\n"
        f"Current working directory: {Path.cwd()}"
    )


def resource_path(*parts: str) -> Path:
    """
    Get path to a resource file within the project.
    
    Args:
        *parts: Path components relative to project root
        
    Returns:
        Path: Absolute path to the resource
        
    Example:
        resource_path("config", "feeds.yaml")  -> /path/to/project/config/feeds.yaml
        resource_path("data", "news.db")       -> /path/to/project/data/news.db
    """
    return project_root().joinpath(*parts)


def ensure_parent_dir(path: Path) -> None:
    """
    Ensure the parent directory of the given path exists.
    
    Args:
        path: Path whose parent directory should exist
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def env_or_resource(env_var: str, *default_parts: str) -> Path:
    """
    Get path from environment variable or fall back to resource path.
    
    This allows overriding default paths via environment variables while
    maintaining robust defaults relative to the project root.
    
    Args:
        env_var: Environment variable name
        *default_parts: Default path components relative to project root
        
    Returns:
        Path: Absolute path from environment or default
        
    Example:
        env_or_resource("FEEDS_CONFIG", "config", "feeds.yaml")
        # Returns path from FEEDS_CONFIG env var if set, otherwise config/feeds.yaml
    """
    env_path = os.getenv(env_var)
    if env_path:
        path = Path(env_path)
        # Only use the env path if it's absolute, otherwise ignore it
        if path.is_absolute():
            return path
    
    return resource_path(*default_parts)


def safe_open(path, mode: str = 'r', **kwargs):
    """
    Safely open a file with helpful error messages if it doesn't exist.
    
    Args:
        path: Path to the file (str or Path)
        mode: File mode (default: 'r')
        **kwargs: Additional arguments passed to open()
        
    Returns:
        File handle
        
    Raises:
        FileNotFoundError: With detailed context if file doesn't exist
    """
    # Convert to Path if string
    if isinstance(path, str):
        path = Path(path)
    
    if 'w' not in mode and 'a' not in mode and not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}\n"
            f"Project root: {project_root()}\n"
            f"Current working directory: {Path.cwd()}\n"
            f"Expected absolute path: {path.resolve()}"
        )
    
    # Ensure parent directory exists for write operations
    if 'w' in mode or 'a' in mode:
        ensure_parent_dir(path)
    
    return open(path, mode, **kwargs)


# Convenience functions for common paths
def config_path(*parts: str) -> Path:
    """Get path to a config file."""
    return resource_path("config", *parts)


def log_path(*parts: str) -> Path:
    """Get path to a log file."""
    return resource_path("logs", *parts)


def template_path(*parts: str) -> Path:
    """Get path to a template file."""
    return resource_path("templates", *parts)


def output_path(*parts: str) -> Path:
    """Get path to an output file."""
    return resource_path("out", *parts)


def data_path(*parts: str) -> Path:
    """Get path to a data file."""
    return resource_path("data", *parts)
