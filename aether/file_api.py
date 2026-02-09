"""
File API Endpoints

================================================================================
REST API for file system operations in the workspace.
Provides listing, reading, writing, and managing files.
================================================================================
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

# Workspace root - should match the sandbox workspace
WORKSPACE_ROOT = Path("/workspace")


class FileNode(BaseModel):
    name: str
    type: str  # "file" or "directory"
    path: str
    size: int = 0
    children: List["FileNode"] = []


FileNode.model_rebuild()


class FileReadResponse(BaseModel):
    content: str
    path: str


class FileWriteRequest(BaseModel):
    path: str
    content: str


def resolve_path(path: str) -> Path:
    """Resolve a path to absolute path within workspace."""
    # Normalize the path
    normalized = os.path.normpath(path.lstrip("/"))
    resolved = WORKSPACE_ROOT / normalized
    
    # Security check - ensure it's within workspace
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside workspace")
    
    return resolved


@router.get("/list")
async def list_files(
    path: str = Query("/", description="Directory path to list")
) -> Dict[str, Any]:
    """List files and directories in the workspace."""
    try:
        target_path = resolve_path(path)
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        
        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        files: List[FileNode] = []
        
        for item in sorted(target_path.iterdir(), key=lambda x: (x.is_file(), x.name)):
            try:
                relative_path = "/" + str(item.relative_to(WORKSPACE_ROOT))
                
                node = FileNode(
                    name=item.name,
                    type="directory" if item.is_dir() else "file",
                    path=relative_path,
                    size=item.stat().st_size if item.is_file() else 0,
                )
                
                # If directory, recursively list (up to 2 levels)
                if item.is_dir():
                    node.children = []
                    try:
                        for child in sorted(item.iterdir(), key=lambda x: (x.is_file(), x.name)):
                            child_relative = "/" + str(child.relative_to(WORKSPACE_ROOT))
                            node.children.append(FileNode(
                                name=child.name,
                                type="directory" if child.is_dir() else "file",
                                path=child_relative,
                                size=child.stat().st_size if child.is_file() else 0,
                            ))
                    except PermissionError:
                        pass
                
                files.append(node)
            except Exception as e:
                logger.warning(f"Error processing {item}: {e}")
        
        return {
            "path": path,
            "files": files,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/read")
async def read_file(
    path: str = Query(..., description="File path to read")
) -> FileReadResponse:
    """Read the contents of a file."""
    try:
        target_path = resolve_path(path)
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not target_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # Size limit (10MB)
        max_size = 10 * 1024 * 1024
        if target_path.stat().st_size > max_size:
            raise HTTPException(status_code=413, detail="File too large (max 10MB)")
        
        content = target_path.read_text(encoding="utf-8", errors="replace")
        
        return FileReadResponse(
            content=content,
            path=path,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write")
async def write_file(request: FileWriteRequest) -> Dict[str, str]:
    """Write content to a file."""
    try:
        target_path = resolve_path(request.path)
        
        # Create parent directories if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        target_path.write_text(request.content, encoding="utf-8")
        
        return {
            "status": "success",
            "path": request.path,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error writing file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
async def delete_file(
    path: str = Query(..., description="File or directory to delete")
) -> Dict[str, str]:
    """Delete a file or directory."""
    try:
        target_path = resolve_path(path)
        
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        
        if target_path.is_dir():
            import shutil
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
        
        return {
            "status": "success",
            "path": path,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mkdir")
async def create_directory(
    path: str = Query(..., description="Directory path to create")
) -> Dict[str, str]:
    """Create a new directory."""
    try:
        target_path = resolve_path(path)
        
        if target_path.exists():
            raise HTTPException(status_code=409, detail="Directory already exists")
        
        target_path.mkdir(parents=True, exist_ok=False)
        
        return {
            "status": "success",
            "path": path,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))
