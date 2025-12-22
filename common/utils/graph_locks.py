"""
Graph-level locking mechanism to prevent concurrent operations on the same graph.
Uses threading.Lock which works for both sync and async contexts.
"""
import threading
import logging
from typing import Dict
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Module-level lock management
_graph_locks: Dict[str, threading.Lock] = {}
_locks_dict_lock = threading.Lock()

# Global rebuild lock (only one rebuild at a time across all graphs)
_rebuild_lock = threading.Lock()
_currently_rebuilding_graph: str = None
_rebuild_graph_lock = threading.Lock()  # Protects _currently_rebuilding_graph


def get_graph_lock(graphname: str) -> threading.Lock:
    """Get or create a lock for a specific graph."""
    with _locks_dict_lock:
        if graphname not in _graph_locks:
            _graph_locks[graphname] = threading.Lock()
            logger.debug(f"Created new lock for graph: {graphname}")
        return _graph_locks[graphname]


def acquire_graph_lock(graphname: str, operation: str = "operation") -> bool:
    """
    Try to acquire lock for a graph. Returns True if acquired, False if already locked.
    
    Args:
        graphname: Name of the graph to lock
        operation: Description of the operation (for logging)
    """
    lock = get_graph_lock(graphname)
    acquired = lock.acquire(blocking=False)
    
    if acquired:
        logger.info(f"Lock acquired for graph '{graphname}' - {operation}")
    else:
        logger.warning(f"Lock already held for graph '{graphname}' - {operation} blocked")
    
    return acquired


def release_graph_lock(graphname: str, operation: str = "operation"):
    """
    Release the lock for a graph.
    
    Args:
        graphname: Name of the graph to unlock
        operation: Description of the operation (for logging)
    """
    lock = get_graph_lock(graphname)
    if lock.locked():
        lock.release()
        logger.info(f"Lock released for graph '{graphname}' - {operation} completed")


def raise_if_locked(graphname: str, operation: str = "operation"):
    """
    Try to acquire lock or raise HTTPException with 409 Conflict status.
    Used for FastAPI endpoints.
    
    Args:
        graphname: Name of the graph to lock
        operation: Description of the operation
        
    Raises:
        HTTPException: 409 Conflict if lock is already held
    """
    if not acquire_graph_lock(graphname, operation):
        raise HTTPException(
            status_code=409,
            detail=f"Another operation is already in progress for graph '{graphname}'. Please wait and try again."
        )

# =====================================================
# Global Rebuild Lock Functions
# =====================================================

def acquire_rebuild_lock(graphname: str, timeout: float = 0.1) -> bool:
    """
    Try to acquire the global rebuild lock (only one rebuild at a time across all graphs).
    Returns True if acquired, False if another rebuild is in progress.
    
    Args:
        graphname: Name of the graph requesting rebuild
        timeout: Timeout in seconds (default 0.1)
    """
    global _currently_rebuilding_graph
    
    acquired = _rebuild_lock.acquire(blocking=True, timeout=timeout)
    
    if acquired:
        with _rebuild_graph_lock:
            _currently_rebuilding_graph = graphname
        logger.info(f"Global rebuild lock acquired for graph: {graphname}")
    else:
        logger.warning(f"Rebuild lock busy - another graph is rebuilding. Request from: {graphname}")
    
    return acquired


def release_rebuild_lock(graphname: str):
    """
    Release the global rebuild lock.
    
    Args:
        graphname: Name of the graph releasing rebuild lock
    """
    global _currently_rebuilding_graph
    
    if _rebuild_lock.locked():
        with _rebuild_graph_lock:
            _currently_rebuilding_graph = None
        _rebuild_lock.release()
        logger.info(f"Global rebuild lock released for graph: {graphname}")


def get_rebuilding_graph() -> str:
    """
    Get the name of the graph currently being rebuilt.
    Returns None if no rebuild is in progress.
    """
    with _rebuild_graph_lock:
        return _currently_rebuilding_graph

