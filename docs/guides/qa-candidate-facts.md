# Candidate facts for the Q&A pairs

Raw material pulled from each document — facts with one clear, unambiguous
answer and a page number. **These are not questions yet.** For each one you
use: phrase it as a natural question, write the answer in your own words,
and open the actual document to confirm it before typing it into
`eval/qa_pairs.csv`. That confirmation step is the part that makes this
real evaluation data instead of something I generated for you.

Pick however many you want from each list — you don't need to use every
fact, and the row counts in `drafting-qa-pairs.md` are a guide, not a quota.

---

## working anytime anywhere-TJ0126015ENN.pdf (Eurofound report)

- **p.4** — Cited as: Eurofound (2026), published by the Publications Office
  of the European Union, in Luxembourg.
- **p.4** — Research manager: Oscar Vargas Llave.
- **p.5** — Table of contents: "Effects on work–life balance and health"
  starts on page 41; "Health" specifically starts on page 44.
- **p.11** — The chapter is based on analysis of the European Working
  Conditions Survey (EWCS) and reports from the Network of Eurofound
  Correspondents.

## 2609.28470v1.pdf (StudentBench paper)

- **p.1** — Paper title: "StudentBench: AI and human tutoring yield
  equivalent GRE learning gains."
- **p.1** — First author: Curtis Northcutt (full author list: Curtis
  Northcutt, Inaara Hasmani, Kevin Feng, Trevor Khangi, Andreas Plesner,
  Jonas Mueller).
- **p.1** — The platform collected over 175,000 student–AI messages.
- **p.1** — Learning gains were measured across 2,383 human participants.
- **p.3** — Pre-test and post-test each had 27 questions.

## 2609.28371v1.pdf (Memory-Conditioned Diffusion Model paper)

- **p.1** — Paper title: "Memory-Conditioned Diffusion Model for Generalized
  Langevin Dynamics."
- **p.1** — First author Minglei Yang's affiliation: Fusion Energy Division,
  Oak Ridge National Laboratory, Oak Ridge, TN, USA.
- **p.1** — Second author Sicheng He's affiliation: Department of Mechanical
  and Aerospace Engineering, University of Tennessee, Knoxville, TN, USA.
- **p.3** — The paper's central contribution is described as "a compact,
  recursively updated memory representation."

## the green city accord-KH0126048ENN.pdf

- **p.3** — Premature deaths attributable to air pollution fell by around
  57% between 2005 and 2023.
- **p.3** — Even with that drop, it still implies more than 180,000 deaths
  per year.
- **p.4** — Since 2020, 132 cities have signed the Green City Accord, across
  23 Member States.
- **p.5** — Alessandro Ghinelli, Mayor of Arezzo, signed the Green City
  Accord on April 30, 2021.
- **p.6** — About 90% of reporting cities are on track to meet EU air
  quality standards.

---

## Кошарка.pdf (Basketball — Macedonian)

- **p.1** — Basketball (кошарка) was invented in 1891 by the Canadian James
  Naismith (Џејмс Најсмит).
- **p.1** — The hoop is mounted at a height of 305 centimeters.
- **p.1** — Naismith's original rules numbered 7, of which 6 are still used
  today.
- **p.2** — Naismith developed the game at the YMCA Training School (today
  Springfield College) in Springfield, Massachusetts, USA.
- **p.3** — Women's basketball began in 1892 at Smith College, introduced by
  Senda Berenson, a physical education professor.
- **p.3** — The first women's collegiate basketball game was played on
  March 9, 1893.

## Одбојка.pdf (Volleyball — Macedonian)

- **p.1** — Volleyball is played by two teams of six players, separated by
  a net.
- **p.1** — A team may hit the ball up to three times before it must cross
  the net.
- **p.2** — The net is set at a height of 1.98 meters.
- **p.2** — The ball weighs 300 grams and has a diameter of 65 cm.
- **p.2** — The first rules of volleyball were written by Morgan, together
  with two friends, in early 1896, at a YMCA conference in Springfield.

---

## Scanned documents (all page 1 — confirm against the original Wikipedia
page, not the OCR text, since OCR made small misreads in places)

**ohrid-scanned-en.pdf** (English "Ohrid" article, confidence 88.0%)
- Ohrid's population was over 38,000 as of 2021.
- Ohrid and Lake Ohrid were accepted as UNESCO World Heritage Sites in 1979
  and 1980 respectively.
- Ohrid is nicknamed the "Jerusalem of the Balkans."
- Ohrid is located southwest of Skopje, west of Resen and Bitola.

**ohrid-scanned-mk.pdf** (Macedonian "Охрид" article, confidence 89.4%)
- Охрид е осми град по број на жители во Македонија, со население од
  38.818 (2021 г.).
- Охрид се наоѓа на 135 километри јужно од Тетово.
- Охрид бил главен град на Првото Бугарско Царство во раниот среден век.
- Охридскиот Регион е вклучен во светското наследство на УНЕСКО во 1979 г.

**fudbal-scanned-mk.pdf** (Macedonian "Фудбал" article, confidence 92.2%)
- Еден фудбалски натпревар трае 90 минути (две полувремиња по 45 минути).
- Игралиштето е со должина од 90 до 120 метри и широчина од 45 до 90 метри.
- Пенал ударот се изведува од точка на 11 метри од головата линија.
- Жолт картон по вторпат за истиот играч резултира со црвен картон.

---

## After you fill in the CSV

Send it back and I'll run every question through the real pipeline —
checking whether the retrieved chunk actually matches the `answer_page` you
recorded, and showing you the app's generated answer next to your correct
one. You grade each one (correct / partially correct / wrong / refused)
yourself.
