# Copyright (c) 2025, s and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class UnitTestBankTransactionInfo(UnitTestCase):
	"""
	Unit tests for BankTransactionInfo.
	Use this class for testing individual functions and methods.
	"""

	pass


class IntegrationTestBankTransactionInfo(IntegrationTestCase):
	"""
	Integration tests for BankTransactionInfo.
	Use this class for testing interactions between multiple components.
	"""

	pass
