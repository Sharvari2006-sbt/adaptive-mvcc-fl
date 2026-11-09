"""
Cryptographic and integrity hashing utilities for WAL and Checkpoints.
Uses CRC32 for high-throughput WAL record validation and SHA-256 for checkpoint hashes.
"""
import zlib
import hashlib
from typing import Union

def compute_crc32(payload: Union[str, bytes]) -> str:
    """Computes a hexadecimal 8-character CRC32 checksum of the payload."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    crc = zlib.crc32(payload) & 0xffffffff
    return f"{crc:08x}"

def verify_crc32(payload: Union[str, bytes], expected_checksum: str) -> bool:
    """Verifies CRC32 checksum integrity."""
    return compute_crc32(payload) == expected_checksum.lower()

def compute_sha256(payload: Union[str, bytes]) -> str:
    """Computes SHA-256 hash."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
