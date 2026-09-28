import pandas as pd

df = pd.read_csv("Data/agridata.csv")

print(df.head())
print(df.columns)
print(df.shape)