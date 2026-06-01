from rich.console import Console
import questionary
import cli_helpers

console = Console()

menu_style = questionary.Style([
    ("separator", "fg:#00bcd4 bold"),
])

basic_actions = [
    "Exit",
    "Get nodes",
    "Add node",
    "Delete node",
    "Reset database",
    "Add relationship",
    "Get relationships",
]

node_types = [
    "Student",
    "Lecture",
    "Professor",
    "Exam"
]

additional_actions = [
    "Get notifications",
    "Manage participants for lecture",
    "Search lectures",
    "Grade a student",
    "Connection between people",
    "Connection between nodes"
]

def main():
    while True:
        menu_choices = [
            questionary.Separator("Basic actions"),
            *basic_actions,
            questionary.Separator("Additional actions"),
            *additional_actions,
        ]
        action = questionary.select("What shall we do?",
                                    choices=menu_choices,
                                    style=menu_style).ask()
        if action is None:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        if action == "Exit":
            console.print("[yellow]Goodbye![/yellow]")
            break
        try:
            with cli_helpers.return_to_main_menu_on_cancel():
                if action == "Get nodes":
                    cli_helpers.proceed_with_getting_nodes(None)
                if action == "Add node":
                    cli_helpers.proceed_with_node_adding()
                if action == "Delete node":
                    cli_helpers.proceed_with_node_deletion()
                if action == "Reset database":
                    cli_helpers.proceed_with_database_reset()
                if action == "Add relationship":
                    cli_helpers.proceed_with_adding_relationship()
                if action == "Get relationships":
                    cli_helpers.proceed_with_getting_relationships()
                if action == "Get notifications":
                    cli_helpers.proceed_with_getting_notifications()
                if action == "Manage participants for lecture":
                    cli_helpers.proceed_with_managing_participants_for_lecture()
                if action == "Search lectures":
                    cli_helpers.proceed_with_searching_lectures()
                if action == "Grade a student":
                    cli_helpers.proceed_with_grading_student()
                if action == "Connection between people":
                    cli_helpers.proceed_with_searching_connection_between_people()
                if action == "Connection between nodes":
                    cli_helpers.proceed_with_searching_connection_between_nodes()
        except cli_helpers.ReturnToMainMenu:
            console.print("\n[yellow]Returning to main menu.[/yellow]")


if __name__ == "__main__":
    main()
