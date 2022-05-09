# models.py

# Custom object models

from enum import Enum


class Day(Enum):
    """Map datetime.weekday() to a string"""
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6
