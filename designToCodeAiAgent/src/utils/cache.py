"""
In-Memory Cache Utility (Simplified - No Redis)
Provides caching functionality for API responses and embeddings
"""
import json
import time
from typing import Any, Optional, Dict
import hashlib
from threading import Lock

from src.config import settings


class CacheError(Exception):
    """Raised when cache operations fail"""
    pass


class InMemoryCache:
    """
    Simple in-memory cache (no Redis required)
    
    Note: Cache is lost on app restart
    For production with multiple workers, consider using Redis later
    """
    
    def __init__(self):
        """Initialize in-memory cache"""
        self.enabled = settings.enable_caching
        self.ttl = settings.cache_ttl
        self._cache: Dict[str, tuple[Any, float]] = {}  # key -> (value, expiry_time)
        self._lock = Lock()
        
        if not self.enabled:
            print("ℹ️  Caching disabled")
        else:
            print("✅ Using in-memory cache (no Redis)")
    
    def _make_key(self, prefix: str, identifier: str) -> str:
        """
        Create a cache key
        
        Args:
            prefix: Key prefix (e.g., 'figma', 'component')
            identifier: Unique identifier
            
        Returns:
            Cache key string
        """
        # Hash long identifiers
        if len(identifier) > 100:
            identifier = hashlib.md5(identifier.encode()).hexdigest()
        
        return f"{prefix}:{identifier}"
    
    def _is_expired(self, expiry_time: float) -> bool:
        """Check if cache entry is expired"""
        return time.time() > expiry_time
    
    def _cleanup_expired(self):
        """Remove expired entries (called periodically)"""
        with self._lock:
            expired_keys = [
                key for key, (_, expiry) in self._cache.items()
                if self._is_expired(expiry)
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None
        
        with self._lock:
            if key not in self._cache:
                return None
            
            value, expiry = self._cache[key]
            
            # Check if expired
            if self._is_expired(expiry):
                del self._cache[key]
                return None
            
            return value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if not specified)
            
        Returns:
            True if successful
        """
        if not self.enabled:
            return False
        
        try:
            ttl = ttl or self.ttl
            expiry_time = time.time() + ttl
            
            with self._lock:
                self._cache[key] = (value, expiry_time)
            
            # Cleanup expired entries occasionally (every 100 sets)
            if len(self._cache) % 100 == 0:
                self._cleanup_expired()
            
            return True
            
        except Exception as e:
            print(f"⚠️  Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if successful
        """
        if not self.enabled:
            return False
        
        try:
            with self._lock:
                if key in self._cache:
                    del self._cache[key]
            return True
        except Exception as e:
            print(f"⚠️  Cache delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and not expired
        """
        if not self.enabled:
            return False
        
        with self._lock:
            if key not in self._cache:
                return False
            
            _, expiry = self._cache[key]
            if self._is_expired(expiry):
                del self._cache[key]
                return False
            
            return True
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern
        
        Args:
            pattern: Key pattern (e.g., "figma:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0
        
        try:
            # Convert pattern to prefix matching
            prefix = pattern.replace("*", "")
            
            with self._lock:
                keys_to_delete = [
                    key for key in self._cache.keys()
                    if key.startswith(prefix)
                ]
                
                for key in keys_to_delete:
                    del self._cache[key]
                
                return len(keys_to_delete)
            
        except Exception as e:
            print(f"⚠️  Cache clear pattern error: {e}")
            return 0
    
    def clear_all(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> dict:
        """
        Get cache statistics
        
        Returns:
            Dict with cache stats
        """
        if not self.enabled:
            return {"enabled": False}
        
        with self._lock:
            # Cleanup expired first
            self._cleanup_expired()
            
            total_size = sum(
                len(str(value)) for value, _ in self._cache.values()
            )
            
            return {
                "enabled": True,
                "type": "in-memory",
                "total_keys": len(self._cache),
                "estimated_size_bytes": total_size,
                "estimated_size_mb": round(total_size / (1024 * 1024), 2),
                "note": "Cache is lost on app restart"
            }
    
    def get_or_set(
        self,
        key: str,
        fetch_fn,
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get from cache or fetch and store
        
        Args:
            key: Cache key
            fetch_fn: Function to call if not in cache
            ttl: Time to live in seconds
            
        Returns:
            Cached or fetched value
        """
        # Try to get from cache
        value = self.get(key)
        if value is not None:
            return value
        
        # Not in cache, fetch it
        value = fetch_fn()
        
        # Store in cache
        self.set(key, value, ttl=ttl)
        
        return value


# Global cache instance
cache = InMemoryCache()


def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_func=None
):
    """
    Decorator to cache function results
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live (uses default if None)
        key_func: Function to generate cache key from args
    
    Example:
        @cached("figma_file", ttl=600)
        def get_figma_file(file_id: str):
            # ... expensive operation
            return result
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key_identifier = key_func(*args, **kwargs)
            else:
                # Use first arg as identifier
                key_identifier = str(args[0]) if args else str(kwargs)
            
            cache_key = cache._make_key(prefix, key_identifier)
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


# Example usage
if __name__ == "__main__":
    """Test cache functionality"""
    
    # Set value
    cache.set("test:key1", {"data": "value"})
    
    # Get value
    value = cache.get("test:key1")
    print(f"Cached value: {value}")
    
    # Check exists
    exists = cache.exists("test:key1")
    print(f"Key exists: {exists}")
    
    # Get stats
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")
    
    # Test get_or_set
    def expensive_operation():
        return {"result": "computed"}
    
    result = cache.get_or_set("test:key2", expensive_operation)
    print(f"Get or set result: {result}")
    
    # Clean up
    cache.delete("test:key1")
    cache.delete("test:key2")
    
    print("✅ Cache test complete")
