# Unit tests: the pure conversion logic, no database or web server needed.
from converter import celsius_to_fahrenheit

def test_freezing_point():
    assert celsius_to_fahrenheit(0) == 32.0

def test_boiling_point():
    assert celsius_to_fahrenheit(100) == 212.0

def test_minus_forty_is_equal():
    assert celsius_to_fahrenheit(-40) == -40.0

def test_body_temperature():
    assert celsius_to_fahrenheit(37) == 98.6
