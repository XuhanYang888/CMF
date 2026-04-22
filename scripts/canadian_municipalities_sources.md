# Canadian municipalities source

Primary source (authoritative):
- Statistics Canada, 2021 Census Subdivision (CSD) boundary file
- https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcsd000b21a_e.zip

Municipality filter used:
- Kept CSDTYPE values that represent municipalities or municipal-equivalent local governments
- Excluded reserves, settlements, hamlets, unorganized areas, improvement districts, and other non-municipal CSDs
- Normalized names to lowercase and removed accents before deduplication

Counts:
- Raw CSD rows: 5161
- Unique normalized municipality names written: 3078

Included CSDTYPE codes:
C, CC, CG, CN, CT, CU, CV, CY, DM, LGD, M, MD, MU, MÉ, NH, NL, NV, P, RCR, RGM, RM, SM, SV, T, TC, TI, TK, TV, V, VC, VL, VN
