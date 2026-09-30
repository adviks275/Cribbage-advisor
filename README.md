# Cribbage Advisor

A cribbage strategy tool that uses exact probability, not simulation, to tell you which cards to keep and which card to play.

Enter your six cards and it ranks every possible discard by expected points. Enter the cut and it guides you through pegging one play at a time, estimating what the opponent is likely to hold from the cards you haven't seen yet.

## Features

- **Discard optimizer.** - Tries all 15 ways to keep 4 of your 6 cards and scores each against all 46 possible cut cards. It then adds the                                expected crib (if you're dealer) or subtracts it (if you're pone) to get a net expected value.
- **Exact crib expectation.** - Averages over every possible pair of opponent discards and every cut, grouped by rank so it runs fast.                                        Includes five-card crib flushes and jack-bonus ("nobs") odds.
- **Pegging advisor.** - For each legal play it shows three things:
                          - points you score now;
                          - the chance the opponent has no playable card and must say "go", computed from hypergeometric probabilities;
                          - the opponent's expected points in reply, assuming they play their best card.
- **Live odds.** - Shows the chance the opponent holds a ten-card or a five, updated as cards are played.
- **Full rules handling.** - Covers 15s, 31, pairs and triples, runs, "go" and last card, and "his heels."

## Usage

Requires Python 3.9+ and nothing beyond the standard library.

```bash
python3 cribbage_advisor.py
```

Enter cards as rank + suit: `5H`, `10D` (or `TD`), `JS`, `AC`, `KC`.

```
Are you pone or dealer? [p/d]: d
Enter your six cards: 5H 5D JC 4S 6S KD

Keep · throw   (hand / crib / net expected points)
  1. keep 5♥ 5♦ 4♠ 6♠     throw J♣ K♦   hand 15.96  crib +3.97  net  19.93
  2. keep 5♥ 5♦ J♣ K♦     throw 4♠ 6♠   hand 12.43  crib +4.46  net  16.89
  ...
```

## How it works

| Component | Method |

| Hand scoring | Checks every card subset for 15s and scores pairs and runs from rank counts. Results are cached. |
| Hand EV | Exact average over all 46 remaining cut cards |
| Crib EV | Exact sum over the unseen cards (opponent's two discards plus the cut), grouped by rank |
| Opponent reply | Hypergeometric P(opponent holds none of a set of cards) = C(U−m, n) / C(U, n) |
| Play ranking | Points now + P(forces go) − expected opponent reply |
