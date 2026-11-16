from evals.report import predict


def test_predict_maps_score_and_hidden_to_labels():
    assert predict(0, None) == "not_relevant"
    assert predict(30, None) == "relevant"
    assert predict(180, None) == "relevant"
    assert predict(0, "qty 1 below your minimum 2") == "hidden_by_qty"
    assert predict(130, "qty 1 below your minimum 2") == "hidden_by_qty"
