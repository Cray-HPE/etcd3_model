"""
Utility Functions to Support Models and Schemas


Copyright 2019, Cray Inc. All rights reserved.

"""
import re


def clean_desc(desc):
    """Clean up whitespace in description strings.

    """
    clean = re.sub(r"\s+", " ", desc)
    clean = re.sub(r"^\s+", "", clean)
    clean = re.sub(r"\s+$", "", clean)
    return clean
