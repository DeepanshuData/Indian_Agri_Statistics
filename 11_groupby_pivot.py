import pandas as pd

#Load dataset
df=pd.read_csv("Data/agridata.csv")
print("Dataset loaded successfully")
print("shape :",df.shape)

#State-wise Summary
state_summary=df.groupby("state").agg(
    total_area=("area","sum"),
    total_production=("production","sum"),
    average_yield=("yield","mean"),
    number_of_records=("crop","count")
)
print("\nState-wise Summary :")
print(state_summary)

#Crop-wise Summary
crop_summary=df.groupby("crop").agg(
    total_area=("area","sum"),
    total_production=("production","sum"),
    average_yield=("yield","mean"),
    number_of_records=("crop","count")
)
print("\nCrop-wise Summary :")
print(crop_summary)

#State X Crop pivot Table
state_crop_pivot=pd.pivot_table(
    df,
    values="production",
    index="state",
    columns="crop",
    aggfunc="sum"
)
print("\nState X Crop Production :")
print(state_crop_pivot)
