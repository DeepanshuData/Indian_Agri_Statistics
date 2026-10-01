import pandas as pd
import numpy as np
import time

# Load dataset

df = pd.read_csv("data/agridata.csv")

print("Dataset loaded successfully.")
print(df.shape)


# Python Loop

start_time = time.perf_counter()

crop_area_loop = {}

for i in range(len(df)):
    crop = df["crop"].iloc[i]
    area = df["area"].iloc[i]

    if crop not in crop_area_loop:
        crop_area_loop[crop] = 0

    crop_area_loop[crop] += area

loop_time = time.perf_counter() - start_time


print("\nPython Loop Result:")
print(crop_area_loop)

print("\nPython Loop Time:", loop_time)

# NumPy

start_time = time.perf_counter()

crops = df["crop"].to_numpy()
areas = df["area"].to_numpy()

unique_crops = np.unique(crops)

crop_area_numpy = {}

for crop in unique_crops:
    total_area = np.sum(areas[crops == crop])
    crop_area_numpy[crop] = total_area

numpy_time = time.perf_counter() - start_time


print("\nNumPy Result:")
print(crop_area_numpy)

print("\nNumPy Time:", numpy_time)

#Compare Results

print("\nResults are same:")
print(crop_area_loop == crop_area_numpy)

# Compare Speed

if numpy_time > 0:

    speed_difference = loop_time / numpy_time

    print("\nSpeed Difference:", speed_difference, "times")