import pandas as pd

def load_data(file_path):
    return pd.read_csv(file_path)

def filter_by_area(df,minimum_area):
    return df[df["area"]>minimum_area]

def filter_by_production(df,minimum_production):
    return df[df["production"]>minimum_production]

def filter_by_crop(df,crop_name):
    return df[df["crop"]==crop_name]

def filter_by_state(df,state_name):
    return df[df["state"]==state_name]
