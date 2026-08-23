from app.taxonomy.classifier import get_classifier


def test_dishwasher_classified_correctly():
    c = get_classifier()
    res = c.classify("PDSH4816AF Dishwasher SS - Display Only")
    assert res.status == "RESOLVED"
    assert res.classpath == "Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers"


def test_cutoff_disc_classified_correctly():
    c = get_classifier()
    res = c.classify('49-94-0013 Milw 5"x.045"x7/8" Metal Cut Off Disc')
    assert res.status == "RESOLVED"
    assert "Cut-Off Discs" in res.classpath


def test_unknown_category_is_honestly_unresolved():
    c = get_classifier()
    res = c.classify("16-24 Adjust Hanger")
    assert res.status == "UNRESOLVED"
    assert res.classpath is None
