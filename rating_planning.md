# Plan for Rating

## Basic Information

Most contests have honor rolls with 5 levels, named Group 1 to Group 5.  
Group 1 is highest, and typically has a lot less people than Group 5.  
It could be possible to account for number of people in the groups within the scoring formula.  
Almost all contests have Group 1 as perfect (or near-perfect for high tier contest).  
Typically anyone with results worth noting appears on the honor roll.  
Gauss only has a (long) list of perfect scores, and is split into Grade 7 and Grade 8 version.  
Pascal, Cayley, and Fermat do not have honor rolls for 2026, but do have them for previous years.  
Tier 1 is highest, and tier 5 is lowest.  

## Contests

| Tier | Contest |
| --- | --- |
| 1 | Euclid |
| 1.5 | CSMC |
| 2 | CIMC |
| 3 | Fermat |
| 3 | Hypatia |
| 3.5 | Cayley |
| 3.5 | Galois |
| 4 | Pascal |
| 4 | Fryer |
| 5 | Gauss (7+8) |

## Scoring Idea

Rate contestants from 0 to 100 score

Formula should be simple  
Takes into account skill + consistency  
Give higher score to contestants who appear in more honor rolls  
Can approximate that going down one contest tier results in going up one honor roll group on average.

### Per-result

$$P = \text{max}(100 - \alpha(t - 1) - \beta(g - 1), 0)$$

$\alpha$ and $\beta$ are hyperparameters.  
Decay based on year? Divide by $2$ for every year that passes.  

### Overall

$$\text{Score} = \alpha \cdot P_\text{avg} + \beta \cdot (1 - e^{\gamma n})$$

$\alpha$, $\beta$, and $\gamma$ are hyperparameters (different from above).  

Instead of $P_\text{avg}$, consider using a weighted sum of top results, where the best results are weighted the most, and it only takes a certain constant of top results. This also eliminates the need for the second term.


### ML Idea

Machine learning model where a score is imputed and the model tries to guess that score.  
Then once it's good, regression to find one number.  