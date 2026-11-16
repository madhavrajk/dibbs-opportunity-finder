from app.contracts import fmt_nsn, fmt_sol, pdf_url, record_url


def test_links_from_raw_solicitation():
    assert record_url("SPE4A527Q0073") == "https://www.dibbs.bsm.dla.mil/rfq/rfqrec.aspx?sn=SPE4A527Q0073"
    assert pdf_url("SPE4A527Q0073") == "https://dibbs2.bsm.dla.mil/Downloads/RFQ/3/SPE4A527Q0073.PDF"
    assert pdf_url("SPE4A627T065C") == "https://dibbs2.bsm.dla.mil/Downloads/RFQ/C/SPE4A627T065C.PDF"


def test_display_formats_match_dibbs():
    assert fmt_nsn("3040017160450") == "3040-01-716-0450"
    assert fmt_nsn("5365LN0021113") == "5365LN0021113"
    assert fmt_sol("SPE4A527Q0073") == "SPE4A5-27-Q-0073"
