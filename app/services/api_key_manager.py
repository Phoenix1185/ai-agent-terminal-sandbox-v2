"""
API Key Manager for Multi-Machine Consistency
Ensures API keys work across all Fly.io machines using volume storage.
"""

import os
import json
import secrets
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from app.core.config import settings


class APIKeyManager:
    """
    Manages API keys stored on the Fly.io volume.
    All machines share the same volume-mounted key storage.
    """

    def __init__(self):
        self.keys_dir = Path(settings.VOLUME_PATH) / "api_keys"
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        self.keys_file = self.keys_dir / "keys.json"
        self.master_key_file = self.keys_dir / "master.key"
        self.keys: Dict[str, dict] = self._load_keys()
        self._ensure_master_key()

    def _load_keys(self) -> Dict[str, dict]:
        """Load API keys from volume storage"""
        if self.keys_file.exists():
            try:
                with open(self.keys_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load API keys: {e}")
                return {}
        return {}

    def _save_keys(self):
        """Save API keys to volume storage (shared across all machines)"""
        try:
            with open(self.keys_file, "w") as f:
                json.dump(self.keys, f, indent=2)
            # Also sync to backup
            backup_file = self.keys_dir / "keys.backup.json"
            with open(backup_file, "w") as f:
                json.dump(self.keys, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save API keys: {e}")

    def _ensure_master_key(self):
        """Ensure master API key exists and is consistent"""
        # Check environment first (Fly.io secrets)
        env_key = os.environ.get("API_KEY")

        if env_key:
            # Use environment key as master
            master_hash = hashlib.sha256(env_key.encode()).hexdigest()[:16]
            self.keys["master"] = {
                "hash": master_hash,
                "name": "Master Key",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": None,
                "permissions": ["*"],
                "source": "env"
            }
            self._save_keys()

            # Save master key reference
            with open(self.master_key_file, "w") as f:
                f.write(master_hash)
        else:
            # Check if we have a stored master
            if "master" not in self.keys:
                # Generate new master key
                new_key = self.generate_key("Master Key", permissions=["*"])
                print(f"🔑 Generated new master API key: {new_key}")

    def generate_key(
        self,
        name: str,
        permissions: List[str] = None,
        expires_days: Optional[int] = None,
        rate_limit: int = 1000
    ) -> str:
        """
        Generate a new API key.

        Args:
            name: Descriptive name for the key
            permissions: List of allowed endpoints (["*"] for all)
            expires_days: Days until expiration (None = never)
            rate_limit: Max requests per hour

        Returns:
            The generated API key (store this securely!)
        """
        # Generate key
        key = f"phx_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = (datetime.utcnow() + timedelta(days=expires_days)).isoformat()

        # Store key info (never store the actual key, only hash)
        self.keys[key_hash] = {
            "hash": key_hash,
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
            "permissions": permissions or ["*"],
            "rate_limit": rate_limit,
            "request_count": 0,
            "last_used": None,
            "active": True,
            "source": "generated"
        }

        self._save_keys()

        return key

    def verify_key(self, key: str) -> bool:
        """Verify an API key against stored hashes"""
        if not key:
            return False

        # Check master key from env first
        env_key = os.environ.get("API_KEY")
        if env_key and key == env_key:
            return True

        # Check stored keys
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        if key_hash not in self.keys:
            return False

        key_data = self.keys[key_hash]

        # Check if active
        if not key_data.get("active", True):
            return False

        # Check expiration
        if key_data.get("expires_at"):
            expires = datetime.fromisoformat(key_data["expires_at"])
            if datetime.utcnow() > expires:
                return False

        # Update usage stats
        key_data["request_count"] = key_data.get("request_count", 0) + 1
        key_data["last_used"] = datetime.utcnow().isoformat()
        self._save_keys()

        return True

    def get_key_info(self, key_hash: str) -> Optional[dict]:
        """Get information about a key by its hash"""
        return self.keys.get(key_hash)

    def list_keys(self) -> List[dict]:
        """List all API keys (without sensitive data)"""
        return [
            {
                "hash": k[:16] + "...",
                "name": v["name"],
                "created_at": v["created_at"],
                "expires_at": v.get("expires_at"),
                "permissions": v["permissions"],
                "request_count": v.get("request_count", 0),
                "last_used": v.get("last_used"),
                "active": v.get("active", True)
            }
            for k, v in self.keys.items()
        ]

    def revoke_key(self, key_hash: str) -> bool:
        """Revoke an API key"""
        if key_hash in self.keys:
            self.keys[key_hash]["active"] = False
            self._save_keys()
            return True
        return False

    def delete_key(self, key_hash: str) -> bool:
        """Delete an API key permanently"""
        if key_hash in self.keys and self.keys[key_hash].get("source") != "env":
            del self.keys[key_hash]
            self._save_keys()
            return True
        return False

    def update_permissions(self, key_hash: str, permissions: List[str]) -> bool:
        """Update key permissions"""
        if key_hash in self.keys:
            self.keys[key_hash]["permissions"] = permissions
            self._save_keys()
            return True
        return False

    def check_permission(self, key: str, endpoint: str) -> bool:
        """Check if key has permission for an endpoint"""
        # Master key from env has all permissions
        env_key = os.environ.get("API_KEY")
        if env_key and key == env_key:
            return True

        key_hash = hashlib.sha256(key.encode()).hexdigest()
        key_data = self.keys.get(key_hash)

        if not key_data:
            return False

        permissions = key_data.get("permissions", [])

        # Wildcard permission
        if "*" in permissions:
            return True

        # Check specific endpoint permission
        return endpoint in permissions

    def rotate_master_key(self) -> str:
        """Rotate the master API key (generates new one, invalidates old)"""
        # Revoke old master
        for k, v in self.keys.items():
            if v.get("source") == "env":
                v["active"] = False

        # Generate new master
        new_key = self.generate_key("Rotated Master Key", permissions=["*"])

        # Update source
        key_hash = hashlib.sha256(new_key.encode()).hexdigest()
        self.keys[key_hash]["source"] = "env_rotated"
        self._save_keys()

        return new_key

    def sync_from_env(self):
        """Sync keys from environment variables (for Fly.io secrets updates)"""
        env_key = os.environ.get("API_KEY")
        if env_key:
            key_hash = hashlib.sha256(env_key.encode()).hexdigest()
            if key_hash not in self.keys:
                self.keys[key_hash] = {
                    "hash": key_hash,
                    "name": "Master Key (Env)",
                    "created_at": datetime.utcnow().isoformat(),
                    "expires_at": None,
                    "permissions": ["*"],
                    "source": "env"
                }
                self._save_keys()


# Global instance
api_key_manager = APIKeyManager()
