import os
import json
from pathlib import Path
from typing import Literal, get_args
import dotenv
from neo4j import GraphDatabase
from datetime import datetime

dotenv.load_dotenv()

uri = os.environ["NEO4J_URI"]
username = os.environ["USERNAME"]
password = os.environ["PASSWORD"]
AUTH = (username, password)
SEED_QUERY_PATH = Path(__file__).with_name("seed_database.cypher")

labels = Literal["Lecture", "Professor", "Student", "Exam"]
relationships = Literal["EXAMINES", "HAS_EXAM", "HAS_GRADE", "HEARS", "REGISTERS", "TEACHES"]
VALID_LABELS = frozenset(get_args(labels))
VALID_RELATIONSHIPS = frozenset(get_args(relationships))


def validate_label(label: str):
    if label not in VALID_LABELS:
        raise ValueError(f"Unsupported node label: {label}")
    return label


def validate_relationship(relationship: str):
    if relationship not in VALID_RELATIONSHIPS:
        raise ValueError(f"Unsupported relationship type: {relationship}")
    return relationship


def load_seed_query():
    return SEED_QUERY_PATH.read_text(encoding="utf-8")


def reset_database():
    seed_query = load_seed_query()

    def reset_and_seed(tx):
        tx.run("MATCH (n) DETACH DELETE n").consume()
        tx.run(seed_query).consume()
        record = tx.run(
            """
            MATCH (n)
            OPTIONAL MATCH ()-[r]->()
            RETURN count(DISTINCT n) AS node_count,
                   count(DISTINCT r) AS relationship_count
            """
        ).single()
        return dict(record)

    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        with driver.session() as session:
            return session.execute_write(reset_and_seed)


def initialize_database_if_empty():
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        records, _, _ = driver.execute_query(
            "MATCH (n) RETURN count(n) AS node_count"
        )
        if records[0]["node_count"]:
            return None

    return reset_database()


def get_nodes(label: labels | None = None):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        if label is None:
            query = "MATCH (n) RETURN elementId(n) AS internal_id, labels(n) AS labels, n"
        else:
            label = validate_label(label)
            query = f"MATCH (n:{label}) RETURN elementId(n) AS internal_id, labels(n) AS labels, n"
        records, summary, _ = driver.execute_query(query)
        return records


def add_node(label: labels, payload: dict):
    label = validate_label(label)

    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = f"""
        CREATE (n:{label})
        SET n = $properties
        RETURN elementId(n) AS id, n
        """
        records, _, _ = driver.execute_query(query, properties=payload)
        record = records[0]
        return {
            "id": record["id"],
            **dict(record["n"]),
        }


def delete_node_by_id(node_id: str):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
        MATCH (n)
        WHERE elementId(n) = $node_id
        WITH n, labels(n) AS labels, properties(n) AS properties
        DETACH DELETE n
        RETURN labels, properties
        """
        records, _, _ = driver.execute_query(query, node_id=node_id)
        return {
            "deleted_count": len(records),
            "deleted_objects": [
                {
                    "labels": record["labels"],
                    "properties": dict(record["properties"]),
                }
                for record in records
            ],
        }


def delete_node_by_properties(label: labels, properties: dict):
    if not properties:
        raise ValueError("Properties cannot be empty")
    label = validate_label(label)

    query = f"""
    MATCH (n:{label})
    WHERE all(key IN keys($properties)
              WHERE toString(n[key]) = toString($properties[key]))
    WITH n, labels(n) AS labels, properties(n) AS properties
    DETACH DELETE n
    RETURN labels, properties
    """

    with GraphDatabase.driver(uri, auth=AUTH) as driver:

        records, _, _ = driver.execute_query(
            query,
            properties=properties,
        )

        return {
            "deleted_count": len(records),
            "deleted_objects": [
                {
                    "labels": record["labels"],
                    "properties": dict(record["properties"]),
                }
                for record in records
            ],
        }


def form_relationship(source_node_id: str,
                      destination_node_id: str,
                      relationship: relationships,
                      relationship_props: dict | None):
    relationship = validate_relationship(relationship)

    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = f"""
               MATCH (n) WHERE elementId(n)=$from_node_id
               MATCH (m) WHERE elementId(m)=$to_node_id
               CREATE (n)-[r:{relationship}]->(m) \n
               """
        query += f"SET r = $relationship_properties RETURN r \n"
        records, _, _ = driver.execute_query(query,
                             from_node_id=source_node_id,
                             to_node_id=destination_node_id,
                             relationship_properties=relationship_props or {})

        return {
            "formed_relationship": len(records) > 0
        }

def remove_relationship(source_id: str, destination_id: str, relationship: relationships):
    relationship = validate_relationship(relationship)

    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = f"""
        MATCH (n)-[r:{relationship}]->(m)
        WHERE elementId(n) = $source_id
          AND elementId(m) = $destination_id
        DELETE r
        RETURN count(r) AS deleted_count
        """

        records, _, _ = driver.execute_query(
            query,
            source_id=source_id,
            destination_id=destination_id,
        )

        return {"deleted_count": records[0]["deleted_count"]}



def get_relationships(r_type: relationships | None,
                      from_label: labels | None,
                      to_label: labels | None,):
    if r_type is not None:
        r_type = validate_relationship(r_type)
    if from_label is not None:
        from_label = validate_label(from_label)
    if to_label is not None:
        to_label = validate_label(to_label)

    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        source_pattern = f"(a:{from_label})" if from_label else "(a)"
        relationship_pattern = f"[r:{r_type}]" if r_type else "[r]"
        destination_pattern = f"(b:{to_label})" if to_label else "(b)"
        query = f"""
        MATCH {source_pattern}-{relationship_pattern}->{destination_pattern}
        RETURN elementId(a) AS source_id,
               labels(a) AS source_labels,
               a AS source,
               type(r) AS relationship_type,
               r AS relationship,
               elementId(b) AS destination_id,
               labels(b) AS destination_labels,
               b AS destination
        """
        records, _, _ = driver.execute_query(query)
        return records

def add_delete_notification(deleted_object: dict, reason: str):
    if not isinstance(deleted_object, dict) or not deleted_object:
        raise ValueError("Deleted object must be a non-empty dictionary")
    if not reason or not reason.strip():
        raise ValueError("Reason cannot be empty")

    content = json.dumps(deleted_object, default=str, sort_keys=True)
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")

    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
        CREATE (n:Notification {
            reason: $reason,
            content: $content,
            createdAt: $created_at
        })
        RETURN n
        """
        records, _, _ = driver.execute_query(
            query,
            content=content,
            reason=reason.strip(),
            created_at=created_at,
        )
        return {
            "notification_added": len(records) > 0
        }


def get_notifications():
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
        MATCH (n:Notification)
        RETURN elementId(n) AS id,
               n.reason AS reason,
               n.content AS content,
               n.createdAt AS created_at
        ORDER BY n.createdAt DESC
        """
        records, _, _ = driver.execute_query(query)
        return records


def get_all_lecture_participants(lecture_id):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
        MATCH (s:Student)-[:HEARS]->(l:Lecture)
        WHERE l.id = $lecture_id
        RETURN elementId(s) AS id,
               s.matriculationNumber AS matriculation_number,
               s.name AS name
        ORDER BY s.name ASC
        """
        records, _, _ = driver.execute_query(query, lecture_id=lecture_id)
        return records

def get_student_by_matr_number(matr_number):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
                MATCH (s:Student)
                WHERE s.matriculationNumber=$matr_number
                RETURN 
                elementId(s) AS id, 
                s.name AS name,
                s.matriculationNumber AS matr_number
                """
        records, _, _ = driver.execute_query(query, matr_number=matr_number)
        if not records:
            return None
        record = records[0]
        return {
            "id": record["id"],
            "name": record["name"],
            "matr_number": record["matr_number"],
        }


def get_registered_exams_for_student(matr_number):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
        MATCH (s:Student {matriculationNumber: $matr_number})
              -[:REGISTERS]->(e:Exam)<-[:HAS_EXAM]-(l:Lecture)
        OPTIONAL MATCH (s)-[g:HAS_GRADE]->(e)
        RETURN elementId(l) AS lecture_internal_id,
               l.id AS lecture_id,
               l.topic AS lecture_topic,
               elementId(e) AS exam_id,
               e.date AS exam_date,
               e.note AS exam_note,
               e.room AS exam_room,
               g.grade AS grade
        ORDER BY l.topic ASC, e.date ASC, e.room ASC
        """
        records, _, _ = driver.execute_query(query, matr_number=matr_number)
        return [
            {
                "lecture_internal_id": record["lecture_internal_id"],
                "lecture_id": record["lecture_id"],
                "lecture_topic": record["lecture_topic"],
                "exam_id": record["exam_id"],
                "exam_date": record["exam_date"],
                "exam_note": record["exam_note"],
                "exam_room": record["exam_room"],
                "grade": record["grade"],
            }
            for record in records
        ]


def get_lecture_by_number(lecture_number):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
        MATCH (l:Lecture)
        WHERE l.id = $lecture_number
        RETURN 
            elementId(l) AS id,
            l.ects AS ects,
            l.topic AS topic,
            l.id AS lecture_id
        """

        records, _, _ = driver.execute_query(
            query,
            lecture_number=lecture_number,
        )

        if not records:
            return None

        record = records[0]

        return {
            "id": record["id"],
            "ects": record["ects"],
            "topic": record["topic"],
            "lecture_id": record["lecture_id"],
        }


def get_lectures_by_name(lecture_name):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
        MATCH (l:Lecture)
        WHERE toLower(l.topic) = toLower($lecture_name)
        RETURN
            elementId(l) AS id,
            l.ects AS ects,
            l.topic AS topic,
            l.id AS lecture_id
        ORDER BY l.id ASC
        """
        records, _, _ = driver.execute_query(query, lecture_name=lecture_name)
        return [
            {
                "id": record["id"],
                "ects": record["ects"],
                "topic": record["topic"],
                "lecture_id": record["lecture_id"],
            }
            for record in records
        ]

class StudentNotRegistered(Exception):
    pass


def grade_student(matriculation_number: str, exam_id: str, grade: int):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        check_registered_query = """
        MATCH (s:Student {matriculationNumber:$matriculation_number})
        MATCH (e:Exam)
        WHERE elementId(e) = $exam_id
        MATCH (s)-[:REGISTERS]->(e)
        RETURN s, e
        """

        records, _, _ = driver.execute_query(
            check_registered_query,
            matriculation_number=matriculation_number,
            exam_id=exam_id,
        )

        if not records:
            raise StudentNotRegistered

        save_grade_query = """
        MATCH (s:Student {matriculationNumber:$matriculation_number})
        MATCH (e:Exam)
        WHERE elementId(e) = $exam_id
        MERGE (s)-[r:HAS_GRADE]->(e)
        WITH r, r.grade AS previous_grade
        SET r.grade = $grade
        RETURN elementId(r) AS id, r.grade AS grade, previous_grade
        """

        records, _, _ = driver.execute_query(
            save_grade_query,
            matriculation_number=matriculation_number,
            exam_id=exam_id,
            grade=grade,
        )

        if not records:
            return None

        record = records[0]

        return {
            "id": record["id"],
            "grade": record["grade"],
            "previous_grade": record["previous_grade"],
        }


def search_lecture(search_string: str):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
        MATCH (p:Professor)-[:TEACHES]->(l:Lecture)
        WHERE 
            toLower(toString(l.ects)) CONTAINS toLower($search_string) OR
            toLower(toString(l.id)) CONTAINS toLower($search_string) OR
            toLower(toString(l.topic)) CONTAINS toLower($search_string) OR
            toLower(toString(p.name)) CONTAINS toLower($search_string)
        RETURN 
            elementId(l) AS id,
            l.id AS lecture_id,
            l.ects AS ects,
            l.topic AS topic
        ORDER BY l.topic ASC
        """

        records, _, _ = driver.execute_query(
            query,
            search_string=search_string.strip(),
        )

        return [
            {
                "id": r["id"],
                "lecture_id": r["lecture_id"],
                "ects": r["ects"],
                "topic": r["topic"],
            }
            for r in records
        ]

def person_exists(person_name: str):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
                MATCH (person)
                WHERE (person:Student OR person:Professor)
                  AND toString(person.name) = $person_name
                RETURN count(person) > 0 AS person_exists
                """
        records, _, _ = driver.execute_query(
            query,
            person_name=person_name,
        )
        return records[0]["person_exists"]


def connection_between_people(first_person_name: str, second_person_name: str):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        are_colleagues = """
                         MATCH (p1:Professor) - [:TEACHES]-> (l:Lecture) <- [:TEACHES] - (p2:Professor)
                         WHERE 
                         toString(p1.name) = $first_person_name AND 
                         toString(p2.name) = $second_person_name
                         RETURN l.topic as topic
                         ORDER BY l.topic ASC
                         """
        records, _, _ = driver.execute_query(
            are_colleagues,
            first_person_name=first_person_name,
            second_person_name=second_person_name,
        )

        if records:
            return {
                "connection": "colleagues",
                "lectures": [r["topic"] for r in records],
            }

        are_classmates = """
                         MATCH (s1:Student) - [:HEARS]-> (l:Lecture) <- [:HEARS] - (s2:Student)
                         WHERE 
                         toString(s1.name) = $first_person_name AND 
                         toString(s2.name) = $second_person_name
                         RETURN l.topic as topic
                         ORDER BY l.topic ASC
                         """
        records, _, _ = driver.execute_query(
            are_classmates,
            first_person_name=first_person_name,
            second_person_name=second_person_name,
        )

        if records:
            return {
                "connection": "classmates",
                "lectures": [r["topic"] for r in records],
            }

        return None

def get_paths_between_nodes(source_id: str, target_id: str):
    with GraphDatabase.driver(uri, auth=AUTH) as driver:
        query = """
            MATCH (a), (b)
            WHERE elementId(a) = $source_id
              AND elementId(b) = $target_id
            MATCH path = (a)-[*1..5]-(b)
            RETURN path, length(path) AS path_length
            ORDER BY path_length ASC
            """
        records, _, _ = driver.execute_query(
            query,
            source_id=source_id,
            target_id=target_id,
        )

        return records
