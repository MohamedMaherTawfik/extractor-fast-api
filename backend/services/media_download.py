"""Opt-in media download boundary; production networking is not configured."""

from abc import ABC, abstractmethod
from pathlib import Path


class MediaDownloadError(RuntimeError):
    pass


class MediaDownloader(ABC):
    @abstractmethod
    def download(self, url: str, destination: Path, timeout: float) -> Path:
        """Download one media URL and return a file inside destination."""


class UnavailableMediaDownloader(MediaDownloader):
    def download(self, url: str, destination: Path, timeout: float) -> Path:
        raise MediaDownloadError("No media downloader is configured")
