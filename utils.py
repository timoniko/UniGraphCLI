from datetime import datetime

def is_valid_date(date_string):
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return "Not a valid date."

def valid_field(string):
    if string is not None:
        if string.strip() != "":
            return True
        return "This field is required."
    else:
        return "This field is required."