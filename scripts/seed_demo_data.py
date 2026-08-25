"""Insert the documented non-sensitive demo creators."""

from backend.db.session import init_database, session_scope
from backend.services.seed_service import seed_demo_data


def main() -> None:
    init_database()
    with session_scope() as session:
        creators_added, accounts_added = seed_demo_data(session)
    print(
        f"Demo seed complete: {creators_added} creators and "
        f"{accounts_added} accounts added."
    )


if __name__ == "__main__":
    main()
