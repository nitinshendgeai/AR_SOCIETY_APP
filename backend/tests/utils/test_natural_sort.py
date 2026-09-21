from app.utils.natural_sort import natural_sort_key


def test_numeric_runs_sort_by_magnitude_not_lexically():
    values = ["A-1702", "A-201", "A-102", "A-101", "A-2101"]
    assert sorted(values, key=natural_sort_key) == [
        "A-101", "A-102", "A-201", "A-1702", "A-2101",
    ]


def test_mixed_prefixed_and_bare_numbers_do_not_raise():
    # Some flats have a wing prefix ("A-101"), some don't ("1101") — the key
    # must stay a single comparable type across both, never int vs str.
    values = ["A-101", "1101", "A-102"]
    assert sorted(values, key=natural_sort_key) == ["1101", "A-101", "A-102"]


def test_case_insensitive():
    assert natural_sort_key("a-101") == natural_sort_key("A-101")


def test_none_and_empty_do_not_raise():
    assert natural_sort_key(None) == ""
    assert natural_sort_key("") == ""
