# src/api/main.py
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
from src.access.rbac import get_current_user, require_permission
from src.pii.anonymizer import MedVietAnonymizer

app = FastAPI(title="MedViet Data API", version="1.0.0")
anonymizer = MedVietAnonymizer()
DATA_PATH = Path("data/raw/patients_raw.csv")


def load_patients() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="Patient dataset not found")
    return pd.read_csv(DATA_PATH)

# --- ENDPOINT 1 ---
@app.get("/api/patients/raw")
@require_permission(resource="patient_data", action="read")
async def get_raw_patients(
    current_user: dict = Depends(get_current_user)
):
    """
    Trả về raw patient data cho admin từ data/raw/patients_raw.csv.
    """
    df = load_patients()
    return JSONResponse(df.head(10).to_dict(orient="records"))

# --- ENDPOINT 2 ---
@app.get("/api/patients/anonymized")
@require_permission(resource="training_data", action="read")
async def get_anonymized_patients(
    current_user: dict = Depends(get_current_user)
):
    """
    Trả về anonymized data cho ml_engineer và admin.
    """
    df = load_patients()
    df_anon = anonymizer.anonymize_dataframe(df)
    return JSONResponse(df_anon.head(10).to_dict(orient="records"))

# --- ENDPOINT 3 ---
@app.get("/api/metrics/aggregated")
@require_permission(resource="aggregated_metrics", action="read")
async def get_aggregated_metrics(
    current_user: dict = Depends(get_current_user)
):
    """
    Trả về aggregated metrics không chứa PII.
    """
    df = load_patients()
    metrics = df["benh"].value_counts().reset_index()
    metrics.columns = ["benh", "count"]
    return JSONResponse(metrics.to_dict(orient="records"))

# --- ENDPOINT 4 ---
@app.delete("/api/patients/{patient_id}")
@require_permission(resource="patient_data", action="delete")
async def delete_patient(
    patient_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Xóa patient theo ID; RBAC chỉ cho phép admin.
    """
    df = load_patients()
    if patient_id not in set(df["patient_id"].astype(str)):
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"status": "deleted", "patient_id": patient_id}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "MedViet Data API"}
