import pandas as pd
from pathlib import Path

file_path = Path("output/districts_intersecting_rivers.csv")
df = pd.read_csv(file_path)

print("Total matching districts:", len(df))
print("\nColumns:")
print(df.columns.tolist())

print("\nFirst 10 matching districts:")
print(df.head(10))

print("\nDistrict count by state:")
print(df["statename"].value_counts())
