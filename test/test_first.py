import unittest
from app.models import *


def test_pytest():
    assert True == True


def test_getUserbyID():
	user = getUserByID(1)
	assert "carina" == user.username


def test_readingBooks():
	user = getUserByID(1)
	assert [] == user.readingBooks()

