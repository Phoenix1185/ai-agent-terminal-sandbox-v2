"""Application configuration with Fly.io volumes"""

from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_NAME: str = "AI Agent Terminal"
    DEBUG: bool = False
    LOG_LEVEL: str = "info"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    WORKERS: int = 1

    # Fly.io
    FLY_REGION: Optional[str] = None
    FLY_ALLOC_ID: Optional[str] = None
    FLY_APP_NAME: Optional[str] = None

    # Volumes (Fly.io persistent storage)
    VOLUME_PATH: str = "/data"
    SANDBOX_DIR: str = "/data/sandbox"
    SESSIONS_DIR: str = "/data/sessions"
    TOOLS_DIR: str = "/data/tools"
    LOGS_DIR: str = "/data/logs"
    BACKUPS_DIR: str = "/data/backups"

    # Persistence
    PERSIST_SESSIONS: bool = True
    SESSION_TIMEOUT: int = 3600  # 1 hour

    # Security
    API_KEY: str = "dev-key-change-in-production"
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Sandbox
    SANDBOX_TIMEOUT: int = 300
    MAX_CONCURRENT_SESSIONS: int = 50
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_COMMANDS: List[str] = [
        # System
        "ls", "cat", "echo", "grep", "find", "pwd", "cd",
        "mkdir", "rm", "cp", "mv", "touch", "head", "tail",
        "wc", "sort", "uniq", "diff", "tar", "gzip", "unzip",
        "wget", "curl", "git", "python", "python3", "node",
        "npm", "pip", "pip3", "cat", "less", "more", "vim",
        "nano", "ps", "top", "htop", "df", "du", "free",
        "whoami", "id", "date", "time", "which", "whereis",
        "chmod", "chown", "ln", "awk", "sed", "cut", "tr",
        "xargs", "jq", "yq", "ffmpeg", "convert", "pdftotext",
        # Package managers
        "apt", "apt-get", "cargo", "gem", "go", "conda",
        # Network
        "ping", "traceroute", "nslookup", "dig", "netstat",
        # Process
        "kill", "pkill", "pgrep", "nohup", "screen", "tmux",
        # Archives
        "zip", "unzip", "7z", "rar",
        # Media
        "ffprobe", "imagemagick", "convert",
        # Database
        "sqlite3", "psql", "mysql",
        # Cloud
        "aws", "gcloud", "az",
        # Build tools
        "make", "cmake", "gcc", "g++", "clang"
    ]

    # Auto-installation
    AUTO_INSTALL_TOOLS: bool = True
    AUTO_INSTALL_TIMEOUT: int = 300

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:////data/app.db"

    # Redis (optional, for multi-machine coordination)
    REDIS_URL: Optional[str] = None

    # Browser
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000
    BROWSER_VIEWPORT_WIDTH: int = 1920
    BROWSER_VIEWPORT_HEIGHT: int = 1080

    # Monitoring
    METRICS_PORT: int = 9091
    ENABLE_METRICS: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
