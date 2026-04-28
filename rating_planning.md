# Plan for Rating

## Basic Information

Most contests have honor rolls with 5 levels, named Group 1 to Group 5.  
Group 1 is highest, and typically has a lot less people than Group 5.  
It could be possible to account for number of people in the groups within the scoring formula.  
Almost all contests have Group 1 as perfect (or near-perfect for high tier contest).  
Typically anyone with results worth noting appears on the honor roll.  
Gauss only has a (long) list of perfect scores, and is split into Grade 7 and Grade 8 version.  
Pascal, Cayley, and Fermat do not have honor rolls for 2026, but do have them for previous years.

## Contest Base Values

| Contest     | Base Value |
| ----------- | ---------- |
| Euclid      | 100        |
| CSMC        | 90         |
| CIMC        | 70         |
| Hypatia     | 60         |
| Fermat      | 60         |
| Galois      | 50         |
| Cayley      | 50         |
| Fryer       | 40         |
| Pascal      | 40         |
| Gauss (7+8) | 15         |

## Group Multipliers

| Group | Multiplier |
| ----- | ---------- |
| I     | 1.00       |
| II    | 0.90       |
| III   | 0.75       |
| IV    | 0.60       |
| V     | 0.45       |

## Scoring Idea

Rate contestants from 0 to 100 score

Formula should be simple  
Takes into account skill + consistency  
Give higher score to contestants who appear in more honor rolls

### Per-result

$$P = C \cdot G \cdot 0.9^{t}$$

$C$ is the contest base value.  
$G$ is the group multiplier.  
$t$ is years ago, using school-year alignment:

- Current 2025/26 school year uses school-year-end $2026$, so $t=0$ for that year.
- 2024/25 has $t=1$, 2023/24 has $t=2$, etc.
- CIMC and CSMC use the following school year end (e.g. 2024 CSMC aligns with 2025 Euclid).

### Overall

$$\text{Score} = \sum_{i=0}^{\text{min}(4, \, |P|-1)} 0.8^i P_i$$

$P$ is the list of scores sorted in a way such that $\text{Score}$ is maximized.  
This means that we calculate a list of adjusted scores, before sorting and then taking the $5$ largest elements.

### ML Idea

Machine learning model where a score is imputed and the model tries to guess that score.  
Then once it's good, regression to find one number.

This shouldn't be published.
