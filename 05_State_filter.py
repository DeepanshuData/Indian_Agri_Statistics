import pandas as pd

df=pd.read_csv("Data/agridata.csv")
filter_data=df[df["state"]=="ANDHRA PRADESH"]

print(filter_data.head(10))
