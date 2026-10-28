"""Optional, read-only local Jev Social runner."""

import asyncio
import json
import shlex
import shutil

from backend.core.config import Settings, get_settings
from backend.social_inventory.exceptions import SocialInventoryError


class JevSocialProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def capability(self) -> dict:
        if not self.settings.jev_social_enabled:
            return {"enabled": False, "reason": "JEV_SOCIAL_ENABLED is false"}
        parts = self._command()
        if not parts or not shutil.which(parts[0]):
            return {"enabled": False, "reason": "Jev executable is not available"}
        return {"enabled": True, "reason": None}

    def _command(self) -> list[str]:
        return [part.strip('"') for part in shlex.split(self.settings.jev_social_command or "", posix=False)]

    async def research(self, *, urls: list[str], goal: str, target_count: int) -> dict:
        capability = self.capability()
        if not capability["enabled"]:
            raise SocialInventoryError("JEV_NOT_AVAILABLE", capability["reason"], status_code=503)
        base = self._command()
        # Verify the installed version's real interface before using any flags.
        help_process = await asyncio.create_subprocess_exec(*base, "research", "--help", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            help_output, _ = await asyncio.wait_for(help_process.communicate(), timeout=min(self.settings.jev_social_timeout, 15))
        except TimeoutError as exc:
            help_process.kill(); await help_process.wait()
            raise SocialInventoryError("JEV_NOT_AVAILABLE", "The installed Jev CLI interface could not be verified.", status_code=503) from exc
        help_text = help_output.decode("utf-8", errors="replace")
        if help_process.returncode != 0 or "--goal" not in help_text or "--limit" not in help_text:
            raise SocialInventoryError("JEV_NOT_AVAILABLE", "The installed Jev CLI does not expose the required read-only research interface.", status_code=503)
        # Arguments are fixed here; React cannot supply a command or switches.
        process = await asyncio.create_subprocess_exec(*base, "research", "--goal", goal, "--limit", str(target_count), *urls, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.settings.jev_social_timeout)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise SocialInventoryError("SOCIAL_PROVIDER_TIMEOUT", "Jev research timed out.", retryable=True, status_code=504) from exc
        if process.returncode != 0:
            raise SocialInventoryError("SOCIAL_PROVIDER_FAILED", "Jev research failed.", status_code=502)
        text = stdout.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"report": text, "evidence": [], "links": urls, "stderr_present": bool(stderr)}
