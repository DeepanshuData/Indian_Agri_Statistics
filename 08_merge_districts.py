import pandas as pd 
df=pd.read_csv("Data/agridata.csv")

coordinates=pd.read_csv("Data/district_coordinates.csv")

merged_data=pd.merge(df,coordinates,on=["district","state"],how="inner")

print(merged_data.head())

print("\nshape:")
print(merged_data.shape)


