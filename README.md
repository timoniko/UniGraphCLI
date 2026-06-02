# University Graph CLI

This is an interactive Python CLI backed by Neo4j. It manages a sample
university graph containing students, professors, lectures, and exams.

## Functionality

The graph stores these node types:

- `Student`: name and matriculation number.
- `Professor`: name and employee number.
- `Lecture`: topic, lecture ID, and ECTS count.
- `Exam`: date, optional note, and optional room.

Nodes can be connected with relationships such as `TEACHES`, `HEARS`,
`EXAMINES`, `HAS_EXAM`, `REGISTERS`, and `HAS_GRADE`.

The basic-actions menu supports:

- Listing nodes by type, including their internal Neo4j IDs and properties.
- Adding or deleting nodes.
- Resetting the database to the bundled sample university graph.
- Adding relationships between nodes by their internal IDs.
- Listing and filtering relationships.

The additional-actions menu supports:

- Viewing notifications created after successful node deletions.
- Adding, listing, or removing participants for a lecture.
- Searching lectures by lecture ID, topic, ECTS count, or professor.
- Assigning a grade to a student registered for an exam.
- Checking whether two people are classmates or colleagues.
- Finding and displaying the shortest paths between any two selected nodes.

Press `Ctrl+C` or cancel a prompt to return to the main menu.

## Run with Docker

Install Docker Desktop or Docker Engine with the Compose plugin. Then run:

```sh
docker compose run --build --rm app
```

The `--build` flag ensures that local Python changes are included in the app
image before it starts. Compose starts an internal Neo4j service, waits until
the database is ready, and opens the interactive menu. Neo4j data is stored in
the `neo4j_data` Docker volume and remains available between runs. The database
is not exposed on host ports, so it does not conflict with other local
services. On the first run, the app automatically loads the sample university
graph. Later runs preserve any changes stored in the volume.

Use `Reset database` from the basic-actions menu to delete all current data and
restore the sample graph.

To use another password, create a local `.env` file based on `.env.example`
before the first run:

```sh
cp .env.example .env
```

Then edit `NEO4J_PASSWORD`. If the persistent database volume was already
created, remove it before changing the initial password:

```sh
docker compose down --volumes
```

To stop the database without deleting its data:

```sh
docker compose down
```

## Run without Docker

Install the dependencies and configure `.env`:

```sh
python -m pip install --requirement requirements.txt
python main.py
```

The application expects `NEO4J_URI`, `USERNAME`, and `PASSWORD` environment
variables. The checked-in `.env.example` is intended for the Docker Compose
setup; use the existing `.env` format when connecting to a manually managed
Neo4j instance.
