import os
import pandas as pd
from sqlalchemy import create_engine
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.preprocessing import LabelEncoder
import pickle

database_url = os.environ["DATABASE_URL"]
model_path = os.getenv("MODEL_PATH", "/app/models.pkl")

print("Loading data...")
engine = create_engine(database_url)
df = pd.read_sql("""
    SELECT operating_airline, origin, dest, distance,
           depdelay, depdel15::int as delayed
    FROM bronze.flights
    WHERE cancelled = FALSE AND depdelay IS NOT NULL
    LIMIT 100000
""", engine)

print(f"Rows: {len(df):,}")

le_airline = LabelEncoder()
le_origin  = LabelEncoder()
le_dest    = LabelEncoder()

df['airline_enc'] = le_airline.fit_transform(df['operating_airline'])
df['origin_enc']  = le_origin.fit_transform(df['origin'])
df['dest_enc']    = le_dest.fit_transform(df['dest'])

X = df[['airline_enc','origin_enc','dest_enc','distance']]

cls_model = LogisticRegression(max_iter=1000)
cls_model.fit(X, df['delayed'])
print("Classification model trained")

mask = df['depdelay'] > 0
reg_model = LinearRegression()
reg_model.fit(X[mask], df[mask]['depdelay'])
print("Regression model trained")

with open(model_path, 'wb') as f:
    pickle.dump({
        'cls': cls_model,
        'reg': reg_model,
        'le_airline': le_airline,
        'le_origin': le_origin,
        'le_dest': le_dest,
    }, f)
print("Done! Models saved.")
