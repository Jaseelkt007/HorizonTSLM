import pandas as pd
from timenet.client import TimeNet
from timenet.registry.factory import default_registry_path

dataset = TimeNet(registry=default_registry_path()).load("timenet/hello-world")
dataset.describe()  # identity, counts, a quick preview

# Each signal converts to Arrow or NumPy, so it drops straight into pandas:
series = dataset.records[0].time_series[0]
df = pd.DataFrame({series.signal: series.to_numpy()})
print(df.head())
