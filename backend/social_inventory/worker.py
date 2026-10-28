"""Standalone durable Social Inventory worker command."""

import argparse
import logging
import os
import socket
import time
from uuid import uuid4

from backend.db.session import init_database, session_scope
from backend.social_inventory.repository import SocialInventoryRepository
from backend.social_inventory.tasks import SocialInventoryTaskRunner

logger = logging.getLogger(__name__)


def work_once(worker_id: str) -> bool:
    with session_scope() as session:
        repository = SocialInventoryRepository(session, "local-operator")
        repository.enqueue_due_syncs()
        run = repository.claim_run(worker_id)
        if run is None: return False
        run_id = str(run.uuid)
    with session_scope() as session:
        from backend.db.models.social_inventory import SocialInventoryRun
        from uuid import UUID
        claimed = session.query(SocialInventoryRun).filter_by(uuid=UUID(run_id), lease_owner=worker_id).one_or_none()
        if claimed is None: return False
        SocialInventoryTaskRunner(session).execute(claimed)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the durable Social Inventory worker")
    parser.add_argument("--once", action="store_true", help="Process at most one state-machine step")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    init_database()
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    while True:
        worked = work_once(worker_id)
        if args.once: break
        if not worked: time.sleep(max(args.poll_seconds, 0.2))


if __name__ == "__main__": main()
