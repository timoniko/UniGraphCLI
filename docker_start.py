from db import initialize_database_if_empty
from main import main


if __name__ == "__main__":
    result = initialize_database_if_empty()
    if result:
        print(
            "Initialized sample database: "
            f"{result['node_count']} nodes, "
            f"{result['relationship_count']} relationships."
        )
    main()
