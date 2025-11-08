"""
Async tools for running sync functions in threads
"""
from anyio import to_thread


async def run_sync(func, /, *args, **kwargs):
    """
    Run a synchronous function in a thread pool to avoid blocking the event loop.
    
    Args:
        func: Synchronous function to run
        *args, **kwargs: Arguments to pass to the function
    
    Returns:
        Result of the function call
    """
    return await to_thread.run_sync(func, *args, **kwargs)

