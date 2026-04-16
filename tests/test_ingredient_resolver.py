from purchasing.ingredient_resolver import classify_ingredient

def test_single_word_generic_is_auto():
    assert classify_ingredient("Chickpeas") == "auto"

def test_two_word_generic_is_auto():
    assert classify_ingredient("Baby Spinach") == "auto"
    assert classify_ingredient("Tomato Sauce") == "auto"
    assert classify_ingredient("Heavy Cream") == "auto"
    assert classify_ingredient("Naan Bread") == "auto"

def test_specialty_single_term_triggers_review():
    assert classify_ingredient("Vadouvan Curry Powder") == "review"
    assert classify_ingredient("Tomato Achaar") == "review"

def test_specialty_cheese_triggers_review():
    assert classify_ingredient("Labneh Cheese") == "review"
    assert classify_ingredient("Paneer Cheese") == "review"

def test_classification_is_case_insensitive():
    assert classify_ingredient("vadouvan curry powder") == "review"
    assert classify_ingredient("BABY SPINACH") == "auto"
