from datetime import date, datetime

from werkzeug.security import check_password_hash


def split_name(full_name):
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def verify_password(stored_password, input_password):
    # Backward compatibility for old plaintext data in PRJ2 seed tables.
    return check_password_hash(stored_password, input_password) or stored_password == input_password


def parse_date(date_string):
    if not date_string:
        return None
    return datetime.strptime(date_string, "%Y-%m-%d").date()


def parse_int(int_string):
    if not int_string:
        return None
    return int(int_string)


def month_labels_between(start_date, end_date):
    labels = []
    cursor = date(start_date.year, start_date.month, 1)
    limit = date(end_date.year, end_date.month, 1)
    while cursor <= limit:
        labels.append(cursor.strftime("%Y-%m"))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return labels


def fill_monthly_series(rows, labels, value_key):
    mapping = {row["month"]: float(row[value_key]) for row in rows}
    return [mapping.get(label, 0.0) for label in labels]
