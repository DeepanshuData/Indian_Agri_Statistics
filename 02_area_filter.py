import pandas as pd
df= pd.read_csv("Data/agridata.csv")

filter_data=df[df["area"]>50000]
print(filter_data.head(10))
