from datetime import date, datetime, timedelta

from app.contracts import ApprovedSource, Profile, Snapshot, Solicitation
from app.match import rank, summary


def S(sol="SPE1C127T0001", nsn="5305012345678", nomen="SCREW,CAP", qty=5, rb=date(2026, 12, 1)):
    return Solicitation(sol=sol, nsn=nsn, fsc=nsn[:4], pr="PR", return_by=rb, qty=qty, ui="EA",
                        nomenclature=nomen, codes="", posted=date(2026, 11, 16))


def snap(*sols, approved=None):
    return Snapshot(posted=date(2026, 11, 16), fetched_at=datetime(2026, 11, 16), source_file="in261116.txt",
                    solicitations=list(sols), approved=approved or {})


def one(profile, sol):
    (m,) = rank(profile, snap(sol))
    return m


def test_cap_not_capacitor():
    assert one(Profile(keywords=["cap"]), S(nomen="CAPACITOR,FIXED")).score == 0


def test_screw_hits_truncated_list():
    n = "SCREW,CAP,HEXAGON HE"
    assert len(n) == 20
    m = one(Profile(keywords=["screw"]), S(nomen=n))
    assert m.score == 30 and m.reasons == ["keyword: screw"]


def test_plural_and_singular():
    assert one(Profile(keywords=["bolt"]), S(nomen="BOLTS,MACHINE")).score == 30
    assert one(Profile(keywords=["bolts"]), S(nomen="BOLT,MACHINE")).score == 30


def test_truncated_last_token():
    n = "BAG,NUCLEAR,BIOLOGIC"
    assert len(n) == 20
    assert one(Profile(keywords=["biological"]), S(nomen=n)).score == 30
    # not 20 chars: no prefix matching
    assert one(Profile(keywords=["biological"]), S(nomen="BAG,BIOLOGIC")).score == 0
    # only the last token may be a cut word
    assert one(Profile(keywords=["biological"]), S(nomen="BIOLOGIC,NUCLEAR,BAGS")).score == 0


def test_multiword_keyword_needs_all_tokens():
    assert one(Profile(keywords=["hex screw"]), S(nomen="SCREW,HEX")).score == 30
    assert one(Profile(keywords=["hex screw"]), S(nomen="SCREW,CAP")).score == 0


def test_nsn_exact_and_one_digit_off():
    assert one(Profile(nsns=["5305012345678"]), S()).score == 100
    assert one(Profile(nsns=["5305012345679"]), S()).score == 0


def test_nsn_with_dashes_hits_and_reason():
    m = one(Profile(nsns=["5305-01-234-5678"]), S())
    assert m.score == 100 and m.reasons == ["NSN 5305-01-234-5678 on your list"]


def test_fsc_not_inside_nsn():
    assert one(Profile(fscs=["5305"]), S(nsn="1234530501234")).score == 0
    m = one(Profile(fscs=["5305"]), S())
    assert m.score == 40 and m.reasons == ["FSC 5305"]


def test_cage_via_approved():
    s = S()
    ap = {s.nsn: [ApprovedSource(nsn=s.nsn, cage="1ABC2", part_no="X")]}
    (m,) = rank(Profile(cage=" 1abc2 "), snap(s, approved=ap))
    assert m.score == 80 and m.reasons == ["You're an approved source (CAGE 1abc2)"]
    (m,) = rank(Profile(cage="9ZZZ9"), snap(s, approved=ap))
    assert m.score == 0


def test_qty_hidden_but_kept_and_counted():
    p = Profile(fscs=["5305"], qty_min=2)
    ms = rank(p, snap(S(sol="SPE1C127T0001", qty=1), S(sol="SPE1C127T0002", qty=None), S(sol="SPE1C127T0003", qty=2)))
    assert len(ms) == 3
    by = {m.sol.sol: m for m in ms}
    assert by["SPE1C127T0001"].hidden_by == "qty 1 below your minimum 2"
    assert by["SPE1C127T0001"].score == 40
    assert by["SPE1C127T0002"].hidden_by is None
    assert by["SPE1C127T0003"].hidden_by is None
    assert summary(ms)["hidden"] == 1 and summary(ms)["matched"] == 2


def test_qty_max():
    m = one(Profile(qty_max=5), S(qty=9))
    assert m.hidden_by == "qty 9 above your maximum 5"


def test_sort_order():
    a = S(sol="SPE1C127T0003", rb=date(2026, 12, 5))
    b = S(sol="SPE1C127T0002", rb=date(2026, 12, 1))
    c = S(sol="SPE1C127T0001", rb=date(2026, 12, 1))
    d = S(sol="SPE1C127T0000", rb=None)
    e = S(sol="SPE1C127T0009", nsn="9999012345678", nomen="WIDGET", rb=date(2026, 11, 20))
    ms = rank(Profile(fscs=["5305"]), snap(a, b, c, d, e))
    assert [m.sol.sol for m in ms] == ["SPE1C127T0001", "SPE1C127T0002", "SPE1C127T0003", "SPE1C127T0000", "SPE1C127T0009"]


def test_no_mutation():
    s = S(nsn="5305-1234567-8"[:0] + "53050123456AB")
    before = (s.sol, s.nsn)
    (m,) = rank(Profile(nsns=["5305-01-234-56AB"], fscs=["5305"]), snap(s))
    assert (m.sol.sol, m.sol.nsn) == before and (s.sol, s.nsn) == before


def test_summary_due_soon():
    t = date.today()
    ms = rank(Profile(fscs=["5305"]), snap(S(sol="SPE1C127T0001", rb=t + timedelta(days=2)),
                                          S(sol="SPE1C127T0002", rb=t + timedelta(days=10)),
                                          S(sol="SPE1C127T0003", nsn="1111012345678")))
    assert summary(ms) == {"total": 3, "matched": 2, "hidden": 0, "due_soon": 1}


def test_padded_short_nomenclature_is_not_treated_as_truncated():
    from app.match import _keyword_hit
    assert not _keyword_hit("PINION", "SPRING,PIN          ")   # padded, PIN is a whole word
    assert _keyword_hit("RAPPELLING", "SNAP LINK,RAPPELLING")       # full 20 chars
    assert _keyword_hit("BIOLOGICAL", "BAG,NUCLEAR,BIOLOGIC")       # cut word, 20 chars
