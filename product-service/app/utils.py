import asyncio
import threading
from functools import wraps
from flask import jsonify

_thread_local = threading.local()


def get_or_create_event_loop():
    try:
        loop = getattr(_thread_local, 'loop', None)
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _thread_local.loop = loop
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _thread_local.loop = loop
        return loop


def run_async(coro):
    loop = get_or_create_event_loop()
    if loop.is_running():
        raise RuntimeError("Event loop is already running. This should not happen in Flask.")
    return loop.run_until_complete(coro)


def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        
        if isinstance(result, tuple) and len(result) == 2:
            return result
        
        if asyncio.iscoroutine(result):
            return run_async(result)
        
        return result
    
    return wrapper

