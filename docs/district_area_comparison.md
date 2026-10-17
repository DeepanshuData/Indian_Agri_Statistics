# District Area Calculation and Census Comparison

## 1. Objective

Calculate Indian district areas directly in PostgreSQL/PostGIS in square kilometres and compare the calculated areas with Census 2011 reference values.

## 2. Methodology

- Used PostGIS `ST_Area` to calculate district areas.
- Calculated spheroid-based areas using the `geography` type.
- Calculated projected areas using the EPSG:6933 equal-area projection.
- Imported Census 2011 district-area reference values into PostgreSQL.
- Matched district records using normalized state and district names.
- Calculated absolute and percentage differences between GIS-derived and Census reference areas.

## 3. Results

The initial comparison matched 550 district records.

| Metric | Result |
|---|---:|
| Matched districts | 550 |
| Average absolute difference | 206.71 km² |
| Average percentage difference | 6.26% |
| Maximum percentage difference | 603.44% |

The comparison between the geography-based and EPSG:6933 area calculations showed differences of 0.0000 km² for the displayed records, after rounding to four decimal places.

## 4. Interpretation

Agreement between the two area-calculation methods supports consistency between those calculations for the displayed records. It does not independently establish the accuracy of the source geometries.

The comparison with Census 2011 revealed substantial discrepancies for some districts. Lakshadweep showed the largest percentage difference in the initial comparison: 603.44%.

Potential explanations include differences in district boundary definitions, source geometry coverage, reference-area conventions, and district matching. These explanations require further verification.

## 5. Limitations

- Only 550 district records matched between the two datasets.
- Census reference values and GIS-derived areas may represent different boundary vintages or area definitions.
- The causes of the largest discrepancies have not yet been confirmed.
- Agreement between calculation methods does not prove that the input geometries are correct.

## 6. Conclusion

District-area calculations and Census reference comparisons have been implemented in PostgreSQL/PostGIS. Initial summary statistics and discrepancy rankings have been generated. The results indicate that the calculation workflow is operational, while the remaining validation work concerns source-data comparability and the causes of large district-level discrepancies.

### Lakshadweep Area Discrepancy

The Lakshadweep district has a reference area of 30 km² in both the source attribute and the Census 2011 comparison table. However, the area calculated from the district geometry using PostGIS is 211.03 km², a difference of 181.03 km². The geometry is valid and contains 23 polygon components. Geography-based and EPSG:6933 equal-area calculations produce consistent results. Inspection of the four largest components' bounding boxes shows no obvious geographic displacement. The underlying cause of the discrepancy remains unconfirmed and requires further verification against the source dataset's metadata and boundary definitions. The calculated area has been retained without modification.
