# -*- coding: utf-8 -*-

"""Test that all Python files meet PEP8 style."""

import os
import pep8
import fnmatch

import unittest

from scripts import PROJECT_DIR

python_dirs = [
    '{}/scripts/'.format(PROJECT_DIR),
    '{}/tests/'.format(PROJECT_DIR)]


def should_check_directory(directory):
    """Check if this directory should be checked."""
    for python_dir in python_dirs:
        if python_dir in directory:
            return True

    return False


class TestPep8(unittest.TestCase):
    """Test that all Python files conform to PEP8 standards."""

    def test_pep8(self):
        """Test that all Python files conform to PEP8 standards."""
        pep8style = pep8.StyleGuide(quiet=True)

        # Find all .py files
        files_list = []
        for root, dirnames, filenames in os.walk(PROJECT_DIR):
            if not should_check_directory(root):
                continue

            for filename in fnmatch.filter(filenames, '*.py'):
                files_list.append(os.path.join(root, filename))

        errors = pep8style.check_files(files_list).total_errors

        error_message = 'Found {} PEP8 errors (and warnings).'.format(errors)
        self.assertEqual(errors, 0, error_message)
