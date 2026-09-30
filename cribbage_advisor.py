#!/usr/bin/env python3
"""
Cribbage Advisor — command-line Python port of the Cribbage Advisor web page.

Flow: choose pone/dealer -> enter your six cards -> see the best keep/throw
options (expected hand +/- crib) -> enter the cut -> get play-by-play
pegging advice while you enter the opponent's cards.

Card input: rank + suit, e.g. 5H, 10D, TD, JS, AC, KC  (suits S H D C).
Run:  python3 cribbage_advisor.py
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from math import comb

# ---------- cards ----------
RANKS = "A23456789TJQK"
SUITS = "SHDC"
SYM = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


@dataclass(frozen=True)
class Card:
    r: int  # 1..13
    s: str  # S H D C

    @property
    def id(self) -> str:
        return RANKS[self.r - 1] + self.s

    def __str__(self) -> str:
        rank = "10" if RANKS[self.r - 1] == "T" else RANKS[self.r - 1]
        return f"{rank}{SYM[self.s]}"

    __repr__ = __str__


DECK = [Card(r, s) for r in range(1, 14) for s in SUITS]


def val(r: int) -> int:
    return min(r, 10)


def parse_card(text: str) -> Card | None:
    t = text.strip().upper().replace("10", "T")
    for k, v in {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}.items():
        t = t.replace(k, v)
    if len(t) != 2 or t[0] not in RANKS or t[1] not in SUITS:
        return None
    return Card(RANKS.index(t[0]) + 1, t[1])


# ---------- hand scoring ----------
@lru_cache(maxsize=None)
def score_ranks(ranks: tuple[int, ...]) -> int:
    """Fifteens, pairs and runs for a sorted tuple of ranks."""
    pts = 0
    vals = [val(r) for r in ranks]
    n = len(ranks)
    for k in range(2, n + 1):
        for combo in combinations(vals, k):
            if sum(combo) == 15:
                pts += 2
    cnt: dict[int, int] = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    for k in cnt.values():
        pts += k * (k - 1)
    d = sorted(cnt)
    i = 0
    while i < len(d):
        j, mult = i, cnt[d[i]]
        while j + 1 < len(d) and d[j + 1] == d[j] + 1:
            j += 1
            mult *= cnt[d[j]]
        if j - i + 1 >= 3:
            pts += (j - i + 1) * mult
        i = j + 1
    return pts


def score_hand(hand: list[Card], starter: Card, is_crib: bool = False) -> int:
    pts = score_ranks(tuple(sorted(c.r for c in hand + [starter])))
    suits = {c.s for c in hand}
    if len(suits) == 1:
        if starter.s in suits:
            pts += 5
        elif not is_crib:
            pts += 4
    if any(c.r == 11 and c.s == starter.s for c in hand):
        pts += 1
    return pts


# ---------- discard analysis ----------
def crib_expect(disc: list[Card], rem: list[Card]) -> float:
    """Exact expected crib score given your two discards, over all
    opponent-discard pairs and cuts drawn from the unseen cards."""
    hist: dict[int, int] = {}
    for c in rem:
        hist[c.r] = hist.get(c.r, 0) + 1
    N = len(rem)
    TP = comb(N, 2)
    dr = [c.r for c in disc]
    ranks = sorted(hist)
    ev = 0.0
    for i, r1 in enumerate(ranks):
        for r2 in ranks[i:]:
            ways = comb(hist[r1], 2) if r1 == r2 else hist[r1] * hist[r2]
            if not ways:
                continue
            h = dict(hist)
            h[r1] -= 1
            h[r2] -= 1
            for r3 in ranks:
                if h[r3] <= 0:
                    continue
                ev += ways * h[r3] / (TP * (N - 2)) * score_ranks(
                    tuple(sorted(dr + [r1, r2, r3])))
    # five-card crib flush
    if disc[0].s == disc[1].s:
        m = sum(1 for c in rem if c.s == disc[0].s)
        ev += 5 * comb(m, 2) * (m - 2) / (TP * (N - 2))
    # nobs: our jack(s)
    sn: dict[str, int] = {}
    for c in rem:
        sn[c.s] = sn.get(c.s, 0) + 1
    for c in disc:
        if c.r == 11:
            ev += sn.get(c.s, 0) / N
    # nobs: opponent's jack(s)
    for j in (c for c in rem if c.r == 11):
        others = [o for o in rem if o != j]
        p = sum((sn[j.s] - 1 - (1 if o.s == j.s else 0)) / (N - 2) for o in others)
        ev += (2 / N) * (p / len(others))
    return ev


@dataclass
class DiscardOption:
    keep: list[Card]
    disc: list[Card]
    hand: float
    crib: float
    net: float


def analyze_discard(six: list[Card], dealer: bool) -> list[DiscardOption]:
    rem = [c for c in DECK if c not in six]
    out = []
    for keep in combinations(six, 4):
        keep = list(keep)
        disc = [c for c in six if c not in keep]
        hand = sum(score_hand(keep, cut) for cut in rem) / len(rem)
        crib = crib_expect(disc, rem)
        out.append(DiscardOption(keep, disc, hand, crib,
                                 hand + crib if dealer else hand - crib))
    return sorted(out, key=lambda o: -o.net)


# ---------- pegging ----------
def peg_points(seq: list[Card], card: Card) -> int:
    nw = seq + [card]
    count = sum(val(c.r) for c in nw)
    pts = 2 if count in (15, 31) else 0
    k = 1
    for c in reversed(seq):
        if c.r != card.r:
            break
        k += 1
    if k >= 2:
        pts += k * (k - 1)
    for L in range(len(nw), 2, -1):
        rs = sorted(c.r for c in nw[-L:])
        if len(set(rs)) == L and rs[-1] - rs[0] == L - 1:
            pts += L
            break
    return pts


def p_none(U: int, n: int, m: int) -> float:
    """P(an n-card hand drawn from U unseen cards holds none of m specific cards)."""
    if n > U - m:
        return 0.0
    return comb(U - m, n) / comb(U, n)


def opp_reply(seq, count, unseen, n_opp) -> tuple[float, float]:
    """(expected opponent points on reply, probability they must say go)."""
    U = len(unseen)
    if not n_opp or not U:
        return 0.0, 1.0
    legal = [c for c in unseen if count + val(c.r) <= 31]
    if not legal:
        return 0.0, 1.0
    pts: dict[int, int] = {}
    for c in legal:
        p = peg_points(seq, c)
        pts[p] = pts.get(p, 0) + 1
    ev, prev, cum = 0.0, 1.0, 0
    for p in sorted(pts, reverse=True):  # opponent plays their best-scoring card
        cum += pts[p]
        ng = p_none(U, n_opp, cum)
        ev += p * (prev - ng)
        prev = ng
    return ev, p_none(U, n_opp, len(legal))


@dataclass
class PlayOption:
    c: Card
    mine: int
    go: float
    oe: float
    score: float


def evaluate_plays(hand, seq, count, unseen, n_opp, opp_go) -> list[PlayOption]:
    rows = []
    for c in hand:
        nc = count + val(c.r)
        if nc > 31:
            continue
        mine = peg_points(seq, c)
        oe, pg = 0.0, 0.0
        if not (nc == 31 or opp_go):
            oe, pg = opp_reply(seq + [c], nc, unseen, n_opp)
        go = pg if nc < 31 else 0.0
        rows.append(PlayOption(c, mine, go, oe, mine + go - oe + 0.001 * val(c.r)))
    return sorted(rows, key=lambda r: -r.score)


# ---------- pegging state machine ----------
class Pegging:
    def __init__(self, keep, six, cut, dealer):
        self.hand = list(keep)
        self.unseen = [c for c in DECK if c not in six and c != cut]
        self.n_opp = 4
        self.count = 0
        self.seq: list[Card] = []
        self.go = [False, False]           # [me, opp]
        self.turn = 1 if dealer else 0      # 0 = me, 1 = opponent
        self.last: int | None = None
        self.peg = [0, 0]
        self.done = False

    def my_legal(self):
        return [c for c in self.hand if self.count + val(c.r) <= 31]

    def award(self):
        if self.last is not None and self.count > 0:
            self.peg[self.last] += 1
            print(f"  Last card · +1 {'you' if self.last == 0 else 'opponent'}")

    def reset_count(self):
        self.count = 0
        self.seq = []
        self.go = [False, False]
        if self.last is not None:
            self.turn = 1 - self.last

    def advance(self):
        for _ in range(8):
            if not self.hand and not self.n_opp:
                if self.count > 0:
                    self.award()
                self.done = True
                return
            ml = self.my_legal()
            if self.turn == 0:
                if ml:
                    return
                if self.go[1] or not self.n_opp:
                    self.award()
                    self.reset_count()
                    continue
                self.go[0] = True
                self.turn = 1
                print("  You say go")
                continue
            else:
                if not self.n_opp or self.go[1]:
                    if not ml:
                        self.award()
                        self.reset_count()
                        continue
                    self.turn = 0
                    continue
                return

    def play_mine(self, c):
        pts = peg_points(self.seq, c)
        self.seq.append(c)
        self.count += val(c.r)
        self.hand.remove(c)
        self.peg[0] += pts
        self.last = 0
        if pts:
            print(f"  +{pts} you")
        if self.count == 31:
            self.reset_count()
        elif not (self.go[1] or not self.n_opp):
            self.turn = 1
        self.advance()

    def opp_play(self, c) -> bool:
        if self.count + val(c.r) > 31:
            print("  That exceeds 31")
            return False
        pts = peg_points(self.seq, c)
        self.seq.append(c)
        self.count += val(c.r)
        self.unseen.remove(c)
        self.n_opp -= 1
        self.peg[1] += pts
        self.last = 1
        if pts:
            print(f"  +{pts} opponent")
        if self.count == 31:
            self.reset_count()
        elif not self.go[0]:
            self.turn = 0
        self.advance()
        return True

    def opp_says_go(self):
        self.go[1] = True
        if not self.my_legal():
            self.award()
            self.reset_count()
        else:
            self.turn = 0
        self.advance()

    def odds_line(self) -> str:
        if not self.n_opp:
            return ""
        U = len(self.unseen)
        h10 = sum(1 for c in self.unseen if val(c.r) == 10)
        h5 = sum(1 for c in self.unseen if c.r == 5)
        return (f"opp holds {self.n_opp} · P(ten) {round((1 - p_none(U, self.n_opp, h10)) * 100)}%"
                f" · P(five) {round((1 - p_none(U, self.n_opp, h5)) * 100)}% · unseen {U}")


# ---------- CLI ----------
def ask_card(prompt: str, allowed) -> Card:
    while True:
        c = parse_card(input(prompt))
        if c is None:
            print("  Enter a card like 5H, 10D, JS, AC.")
        elif not allowed(c):
            print(f"  {c} isn't available here.")
        else:
            return c


def run_hand():
    role = ""
    while role not in ("p", "d"):
        role = input("Are you pone or dealer? [p/d]: ").strip().lower()[:1]
    dealer = role == "d"

    print("\nEnter your six cards (e.g. 5H 5D JC 4S 6S KD):")
    six: list[Card] = []
    while len(six) < 6:
        for tok in input(f"  {6 - len(six)} more: ").replace(",", " ").split():
            c = parse_card(tok)
            if c is None:
                print(f"  Couldn't read '{tok}'.")
            elif c in six:
                print(f"  {c} already entered.")
            elif len(six) < 6:
                six.append(c)
    print("  Hand:", " ".join(map(str, six)))

    print("\nKeep · throw   (hand / crib / net expected points)")
    opts = analyze_discard(six, dealer)[:5]
    for i, o in enumerate(opts, 1):
        sign = "+" if dealer else "−"
        print(f"  {i}. keep {' '.join(map(str, o.keep)):<16} throw {' '.join(map(str, o.disc)):<8}"
              f" hand {o.hand:5.2f}  crib {sign}{o.crib:4.2f}  net {o.net:6.2f}")
    pick = input("Choose option [1]: ").strip()
    choice = opts[int(pick) - 1] if pick.isdigit() and 1 <= int(pick) <= len(opts) else opts[0]
    print(f"  Keeping {' '.join(map(str, choice.keep))} · expected {choice.net:.2f} net")

    cut = ask_card("\nCut (starter) card: ", lambda c: c not in six)
    msg = f"  Your hand scores {score_hand(choice.keep, cut)}"
    if cut.r == 11:
        msg += f" · his heels, +2 to {'you' if dealer else 'opponent'}"
    print(msg)

    print("\n--- Pegging ---")
    pg = Pegging(choice.keep, six, cut, dealer)
    pg.advance()
    while not pg.done:
        seq = " ".join(map(str, pg.seq)) or "(new count)"
        print(f"\nCount {pg.count} · {seq} · you {pg.peg[0]}, opp {pg.peg[1]}")
        odds = pg.odds_line()
        if odds:
            print("  " + odds)
        if pg.turn == 0:
            rows = evaluate_plays(pg.hand, pg.seq, pg.count, pg.unseen, pg.n_opp,
                                  pg.go[1] or not pg.n_opp)
            for r in rows:
                print(f"    {str(r.c):<4} score {r.score:+.2f}  (now {r.mine}, "
                      f"go {r.go * 100:.0f}%, opp back {r.oe:.2f})")
            best = rows[0]
            print(f"  Suggest: play {best.c}")
            legal = [r.c for r in rows]
            txt = input(f"Your play [{best.c.id}]: ").strip()
            c = best.c if not txt else parse_card(txt)
            if c not in legal:
                print("  Not a legal card from your hand.")
                continue
            pg.play_mine(c)
        else:
            txt = input("Opponent's card (or 'go'): ").strip().lower()
            if txt == "go":
                pg.opp_says_go()
                continue
            c = parse_card(txt)
            if c is None or c not in pg.unseen:
                print("  Not an unseen card.")
                continue
            pg.opp_play(c)

    print(f"\nPegging over · you {pg.peg[0]}, opponent {pg.peg[1]} · hand counts next")


def main():
    print("Cribbage Advisor\n")
    while True:
        run_hand()
        if input("\nNew hand? [y/n]: ").strip().lower()[:1] != "y":
            break
        print()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nBye.")
