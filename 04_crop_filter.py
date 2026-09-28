import pandas as pd
df=pd.read_csv("Data/agridata.csv")

filter_data=df[df["crop"]=="Rice"]
print(filter_data.head(10))