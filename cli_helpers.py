import json
from contextlib import contextmanager

from utils import valid_field
import questionary
from db import (
    add_node,
    delete_node_by_id,
    delete_node_by_properties,
    form_relationship,
    get_nodes,
    get_notifications,
    get_relationships,
    add_delete_notification,
    get_all_lecture_participants,
    get_student_by_matr_number,
    get_lecture_by_number,
    get_lectures_by_name,
    remove_relationship,
    grade_student,
    search_lecture,
    person_exists,
    connection_between_people,
    get_paths_between_nodes,
    reset_database,
    StudentNotRegistered,
    AlreadyGraded,
)
from rich.console import Console
from rich.table import Table
from schemas import node_schemas
from typing import Literal
from questionary import Choice

console = Console()
node_types = list(node_schemas)

node_retrieval_modes = {
    "All nodes": ("all", None),
    "Lectures": ("lectures", "Lecture"),
    "Students": ("students", "Student"),
    "Professors": ("professors", "Professor"),
    "Exams": ("exams", "Exam"),
}

relationship_types = [
    "EXAMINES",
    "HAS_EXAM",
    "HAS_GRADE",
    "HEARS",
    "REGISTERS",
    "TEACHES",
]


class ReturnToMainMenu(Exception):
    pass


@contextmanager
def return_to_main_menu_on_cancel():
    original_ask = questionary.Question.ask

    def ask_or_return_to_menu(question, *args, **kwargs):
        answer = original_ask(question, *args, **kwargs)
        if answer is None:
            raise ReturnToMainMenu
        return answer

    questionary.Question.ask = ask_or_return_to_menu
    try:
        yield
    finally:
        questionary.Question.ask = original_ask


def format_properties(properties):
    return "\n".join(
        f"{key}: {value}" for key, value in sorted(dict(properties).items())
    ) or "-"


def proceed_with_getting_nodes(
        mode: Literal["all", "lectures", "students", "professors", "exams"] | None):
    if mode is None:
        selected_mode = questionary.select(
            "Which nodes should be displayed?",
            choices=list(node_retrieval_modes),
        ).ask()
        if not selected_mode:
            return
        mode, label = node_retrieval_modes[selected_mode]
    else:
        labels_by_mode = {
            retrieval_mode: label
            for retrieval_mode, label in node_retrieval_modes.values()
        }
        label = labels_by_mode[mode]

    records = get_nodes(label)
    if not records:
        console.print(f"\n[yellow]No {mode} found.[/yellow]")
        return

    table = Table(title=f"{mode.capitalize()} ({len(records)})", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Properties", style="green")

    for record in records:
        table.add_row(
            str(record["internal_id"]),
            ", ".join(record["labels"]),
            format_properties(record["n"]),
        )

    console.print()
    console.print(table)


def construct_node_payload_with_action(node_type, action: Literal["add", "delete"], return_created=None):
    payload = {}
    fields = node_schemas[node_type]

    if action == "delete":
        field_by_key = {field["key"]: field for field in fields}
        selected_keys = questionary.checkbox(
            "Which properties should the deleted node match?",
            choices=list(field_by_key),
            validate=lambda selected: bool(selected) or "Select at least one property.",
        ).ask()
        if not selected_keys:
            return
        fields = [field_by_key[key] for key in selected_keys]

    for field in fields:
        validator = field.get("validate")
        if action == "delete":
            validator = validator or valid_field
        kwargs = {"validate": validator} if validator else {}
        payload[field["key"]] = questionary.text(field["prompt"], **kwargs).ask()

    summary = ", ".join([f"{k}: {v}" for k, v in payload.items()])
    confirmed = questionary.confirm(
        f"{action.capitalize()} {node_type} with data: ({summary})?"
    ).ask()

    if not confirmed:
        console.print("\n[yellow]Cancelled by user.[/yellow]")
    else:
        if action == "add":
            created = add_node(node_type, payload=payload)
            console.print(f"\n[green]Added {node_type}! ({summary})[/green]")
            if return_created:
                return created

        else:
            reason = questionary.text("Whats the reason of deletion?").ask()
            result = delete_node_by_properties(node_type, payload)
            deleted_count = result["deleted_count"]
            console.print(
                f"\n[green]Deleted {deleted_count} {node_type} node(s)! ({summary})[/green]"
            )
            add_delete_notification(deleted_object={"type": node_type,
                                                    "content": payload}, reason=reason)


def proceed_with_node_adding():
    node_type = questionary.select("What to add?", choices=list(node_schemas.keys())).ask()
    if not node_type:
        return
    construct_node_payload_with_action(node_type, action="add")


def proceed_with_node_deletion():
    knows_id = questionary.select("Do you know node's ID?", choices=['Yes', 'No']).ask()
    if knows_id == 'Yes':
        node_id = questionary.text("What is node's id?", validate=valid_field).ask()
        delete_node_by_id(node_id)
        print(f"Successfully deleted node with id {node_id}")
    else:
        node_type = questionary.select("What to delete", choices=node_types).ask()
        if not node_type:
            return
        construct_node_payload_with_action(node_type, action="delete")


def proceed_with_database_reset():
    confirmed = questionary.confirm(
        "Delete all current data and restore the sample database?"
    ).ask()
    if not confirmed:
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        return

    result = reset_database()
    console.print(
        "\n[green]Database reset complete: "
        f"{result['node_count']} nodes, "
        f"{result['relationship_count']} relationships.[/green]"
    )


def proceed_with_adding_relationship():
    source_node_id = questionary.text("What's the source node's ID?", validate=valid_field).ask()
    if not source_node_id:
        return

    destination_node_id = questionary.text("What's the destination node's ID?", validate=valid_field).ask()
    if not destination_node_id:
        return

    relationship_type = questionary.select(
        "What is the relationship?",
        choices=relationship_types,
    ).ask()
    if not relationship_type:
        return
    confirmed = questionary.confirm("Form the relationship?").ask()
    if not confirmed:
        return

    result = form_relationship(
        source_node_id,
        destination_node_id,
        relationship_type,
        relationship_props=None,
    )
    if result["formed_relationship"]:
        console.print("\n[green]Successfully added relationship![/green]")
    else:
        console.print(
            "\n[yellow]Relationship was not added. Check that both node IDs exist.[/yellow]"
        )


def proceed_with_getting_relationships():
    relationship_type = questionary.select(
        "Which relationship type should be displayed?",
        choices=["Any", *relationship_types],
    ).ask()
    if not relationship_type:
        return

    source_label = questionary.select(
        "Which source node type should be displayed?",
        choices=["Any", *node_types],
    ).ask()
    if not source_label:
        return

    destination_label = questionary.select(
        "Which destination node type should be displayed?",
        choices=["Any", *node_types],
    ).ask()
    if not destination_label:
        return

    records = get_relationships(
        None if relationship_type == "Any" else relationship_type,
        None if source_label == "Any" else source_label,
        None if destination_label == "Any" else destination_label,
    )
    if not records:
        console.print("\n[yellow]No matching relationships found.[/yellow]")
        return

    table = Table(title=f"Relationships ({len(records)})", show_lines=True)
    table.add_column("Source", style="cyan")
    table.add_column("Relationship", style="magenta")
    table.add_column("Destination", style="green")

    for record in records:
        table.add_row(
            (
                f"{', '.join(record['source_labels'])}\n"
                f"ID: {record['source_id']}\n"
                f"{format_properties(record['source'])}"
            ),
            (
                f"{record['relationship_type']}\n"
                f"{format_properties(record['relationship'])}"
            ),
            (
                f"{', '.join(record['destination_labels'])}\n"
                f"ID: {record['destination_id']}\n"
                f"{format_properties(record['destination'])}"
            ),
        )

    console.print()
    console.print(table)


def proceed_with_getting_notifications():
    records = get_notifications()
    if not records:
        console.print("\n[yellow]No notifications found.[/yellow]")
        return

    table = Table(title=f"Delete notifications ({len(records)})", show_lines=True)
    table.add_column("Created at", style="cyan", no_wrap=True)
    table.add_column("Reason", style="yellow")
    table.add_column("Deleted object", style="green")

    for record in records:
        try:
            content = json.dumps(json.loads(record["content"]), indent=2, sort_keys=True)
        except (TypeError, json.JSONDecodeError):
            content = str(record["content"])
        table.add_row(
            str(record["created_at"]),
            str(record["reason"]),
            content,
        )

    console.print()
    console.print(table)


def proceed_with_managing_participants_for_lecture():
    lookup_mode = questionary.select(
        "How do you want to find the lecture?",
        choices=["By ID", "By name"],
    ).ask()
    if lookup_mode == "By ID":
        lecture_number = questionary.text("What is the lecture number?", validate=valid_field).ask()
        lecture = get_lecture_by_number(lecture_number)
    else:
        lecture_name = questionary.text("What is the lecture name?", validate=valid_field).ask()
        matching_lectures = get_lectures_by_name(lecture_name)
        if len(matching_lectures) == 1:
            lecture = matching_lectures[0]
        elif len(matching_lectures) > 1:
            lecture_choices = {
                f"{lecture['topic']} ({lecture['lecture_id']})": lecture
                for lecture in matching_lectures
            }
            selected_lecture = questionary.select(
                "Multiple lectures found. Which one do you mean?",
                choices=list(lecture_choices),
            ).ask()
            lecture = lecture_choices[selected_lecture]
        else:
            lecture = None

    if not lecture:
        console.print("\n[red]No matching lecture found![/red]")
    else:
        lecture_number = lecture["lecture_id"]
        action = questionary.select("What to do with chosen lecture?",
                                    choices=["Add new participant", "See participants", "Remove a participant"]).ask()
        if action == "Add new participant":
            matr_number = questionary.text("What is student's matriculation number?",
                                           validate=valid_field).ask()
            found_student = get_student_by_matr_number(matr_number)
            if not found_student:
                create_new_student = questionary.select(
                    "Student with this id was not found, do you want to create a new student?",
                    choices=["Yes", "No"],
                ).ask()
                if create_new_student == "Yes":
                    new_student = construct_node_payload_with_action(node_type='Student',
                                                                     action='add',
                                                                     return_created=True)
                    form_relationship(source_node_id=new_student['id'],
                                      destination_node_id=lecture['id'],
                                      relationship="HEARS",
                                      relationship_props=None)
                    console.log(f"\n[green]Successfully created and "
                                f"added {new_student['name']} to {lecture['topic']}![/green]")
            else:
                form_relationship(source_node_id=found_student['id'],
                                  destination_node_id=lecture['id'],
                                  relationship="HEARS",
                                  relationship_props=None)
                console.log(f"\n[green]Successfully added {found_student['name']} to {lecture['topic']}![/green]")
        if action == "See participants":
            lecture_participants = get_all_lecture_participants(lecture_number)
            if not lecture_participants:
                console.print("\n[yellow]No participants in this lecture found.[/yellow]")
            else:
                table = Table(
                    title=f"Participants ({len(lecture_participants)})",
                    show_lines=True,
                )
                table.add_column("ID", style="green", no_wrap=True)
                table.add_column("Matriculation number", style="cyan")
                table.add_column("Name", style="magenta")
                for record in lecture_participants:
                    table.add_row(
                        str(record["id"]),
                        str(record["matriculation_number"]),
                        str(record.get("name", "")),
                    )

                console.print()
                console.print(table)
        if action == "Remove a participant":
            student_matr_number = questionary.text("What is the student's matriculation number?",
                                                   validate=valid_field).ask()
            student = get_student_by_matr_number(student_matr_number)
            if not student:
                console.log("\n[red]No student with this matriculation number![/red]")
            else:
                result = remove_relationship(source_id=student['id'],
                                             destination_id=lecture['id'],
                                             relationship="HEARS")
                if result["deleted_count"]:
                    console.log(f"\n[green]Successfully deregistered {student['name']} "
                                f"{student['matr_number']} from {lecture['topic']}![/green]")
                else:
                    console.log(f"\n[yellow]{student['name']} is not registered "
                                f"for {lecture['topic']}.[/yellow]")


def proceed_with_searching_lectures():
    search_string = questionary.text("Enter lecture's id, topic, ects, or professor.", validate=valid_field).ask()
    lectures = search_lecture(search_string)
    if not lectures:
        console.log("\n[red]No lectures found for this search![/red]")
    else:
        table = Table()
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Lecture ID", style="magenta", no_wrap=True)
        table.add_column("ECTS", style="cyan", no_wrap=True)
        table.add_column("Topic", style="cyan", no_wrap=True)

        for record in lectures:
            table.add_row(
                str(record["id"]),
                str(record["lecture_id"]),
                str(record.get("ects", "")),
                str(record.get("topic", "")),
            )

        console.print()
        console.print(table)


def proceed_with_grading_student():
    matr_number = questionary.text("What is the student's matriculation number?").ask()
    student = get_student_by_matr_number(matr_number)
    if not student:
        console.log("\n[red]No student with this matriculation number![/red]")
    else:
        exam_id = questionary.text("What is the exam's id?", validate=valid_field).ask()
        grade = questionary.text("What is the grade for the exam?", validate=valid_field).ask()
        try:
            grade_student(matr_number, exam_id, grade)
            console.log(f"\n[green]Successfully graded {student['name']} for exam {exam_id}![/green]!")
        except StudentNotRegistered:
            console.log("\n[red]Student not registered for exam![/red]")
        except AlreadyGraded:
            console.log("\n[yellow]This student is already graded for this exam![/yellow]")


def proceed_with_searching_connection_between_people():
    name_of_first_person = questionary.text("What is the name of the first person?").ask()
    if not person_exists(name_of_first_person):
        console.log(f"\n[red]No person named {name_of_first_person} found![/red]")
        return

    name_of_second_person = questionary.text("What is the name of the second person?").ask()
    if not person_exists(name_of_second_person):
        console.log(f"\n[red]No person named {name_of_second_person} found![/red]")
        return

    connection = connection_between_people(name_of_first_person, name_of_second_person)
    if not connection:
        console.log(f"\n[yellow]Looks like {name_of_first_person} "
                    f"and {name_of_second_person} are not connected![/yellow]")
    else:
        connection_type = connection["connection"]
        shared_lectures = connection["lectures"]
        if connection_type == "colleagues":
            console.log(f"\n[green]{name_of_first_person} and {name_of_second_person} are colleagues!"
                        f" They teach [cyan]{', '.join(shared_lectures)}[/cyan].[/green]")
        if connection_type == "classmates":
            console.log(f"\n[green]{name_of_first_person} and {name_of_second_person} are classmates!"
                        f" They attend [cyan]{', '.join(shared_lectures)}[/cyan].[/green]")


def proceed_with_searching_connection_between_nodes():
    first_node_id = get_internal_id_based_on_candidates("first")
    if not first_node_id:
        console.log(f"\n[red]Failed to get first node![/red]")
        return

    second_node_id = get_internal_id_based_on_candidates("second")
    if not second_node_id:
        console.log(f"\n[red]Failed to get second node![/red]")
        return

    paths = get_paths_between_nodes(first_node_id, second_node_id)
    if not paths:
        console.print("\n[yellow]No paths found between the selected nodes.[/yellow]")
        return

    table = Table(title=f"Paths between nodes ({len(paths)})", show_lines=True)
    table.add_column("Source", style="cyan")
    table.add_column("Target", style="green")
    table.add_column("Path", style="magenta")
    table.add_column("Length", style="yellow", justify="right")

    for record in paths:
        path = record["path"]
        table.add_row(
            format_path_endpoint(path.start_node),
            format_path_endpoint(path.end_node),
            format_path(path),
            str(record["path_length"]),
        )

    console.print()
    console.print(table)


def format_path_node(node):
    labels = ", ".join(sorted(node.labels)) or "Node"
    properties = dict(node)
    identifying_keys = (
        "name",
        "topic",
        "id",
        "matriculationNumber",
        "employeeNumber",
        "date",
    )
    details = ", ".join(
        f"{key}: {properties[key]}"
        for key in identifying_keys
        if properties.get(key) not in (None, "")
    )
    return f"{labels} ({details})" if details else labels


def format_path_endpoint(node):
    return f"{format_path_node(node)}\nID: {node.element_id}"


def format_path(path):
    nodes = list(path.nodes)
    parts = [format_path_node(nodes[0])]
    for current_node, relationship, next_node in zip(
            nodes, path.relationships, nodes[1:]):
        if relationship.start_node.element_id == current_node.element_id:
            parts.append(f"-[{relationship.type}]->")
        else:
            parts.append(f"<-[{relationship.type}]-")
        parts.append(format_path_node(next_node))
    return " ".join(parts)



def get_internal_id_based_on_candidates(mode: Literal["first", "second"]):
    node_type_choices = ["Lecture", "Student", "Professor", "Exam"]
    node_type = questionary.select(f"What is the type of {mode} node?",
                                   node_type_choices).ask()
    if node_type == "Student":
        students = get_nodes(label="Student")
        choices = [
            Choice(
                title=f"{s['n']['name']} ({s['n']['matriculationNumber']})",
                value=s["internal_id"],
            )
            for s in students
        ]
        internal_id = questionary.select(
            "Choose student:",
            choices=choices,
        ).ask()
        return str(internal_id) if internal_id else None

    if node_type == "Lecture":
        lectures = get_nodes(label="Lecture")
        choices = [
            Choice(
                title=f"{l['n']['topic']} ({l['n']['ects']}, {l['n']['id']})",
                value=l["internal_id"],
            )
            for l in lectures
        ]
        internal_id = questionary.select(
            "Choose lecture:",
            choices=choices,
        ).ask()

        return str(internal_id) if internal_id else None

    if node_type == "Professor":
        professors = get_nodes(label="Professor")
        choices = [
            Choice(
                title=f"{p['n']['name']} ({p['n']['employeeNumber']})",
                value=p["internal_id"],
            )
            for p in professors
        ]
        internal_id = questionary.select(
            "Choose professor:",
            choices=choices,
        ).ask()

        return str(internal_id) if internal_id else None

    if node_type == "Exam":
        exams = get_nodes(label="Exam")
        choices = [
            Choice(
                title=f"{e['n']['date']} ({e['n']['note']}, {e['n']['room']})",
                value=e["internal_id"],
            )
            for e in exams
        ]
        internal_id = questionary.select(
            "Choose exam:",
            choices=choices,
        ).ask()
        return str(internal_id) if internal_id else None
    else:
        return None








