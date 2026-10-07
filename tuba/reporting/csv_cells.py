"""Keep exported text inert when a CSV is opened in a spreadsheet."""

import re


def spreadsheet_cell(value):
    if isinstance(value, str) and (value.startswith(("\t", "\r", "\n"))
                                  or re.match(r"^[\s\x00-\x1f]*[=+\-@]", value)):
        return "'" + value
    return value
