from app.services.skills import canonical, dedupe, find_in_text


def test_aliases_map_to_the_same_skill():
    assert canonical("ReactJS") == canonical("react") == canonical("React.js")
    assert canonical("Postgres") == canonical("PostgreSQL")
    assert dedupe(["js", "JavaScript", "REST API", "RESTful APIs"]) == ["JavaScript", "REST APIs"]


def test_find_in_text_is_whole_word_and_avoids_false_positives():
    text = "Built dashboards with JavaScript, React.js and Power BI. I excel at teamwork. Advanced Excel."
    found = find_in_text(text)
    assert "JavaScript" in found and "React" in found and "Power BI" in found and "Excel" in found
    assert "Java" not in found  # "JavaScript" must not count as Java
    assert find_in_text("I excel at chess") == []
