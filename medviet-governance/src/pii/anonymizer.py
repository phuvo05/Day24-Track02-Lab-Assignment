# src/pii/anonymizer.py
import hashlib
import re
import secrets

import pandas as pd
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from faker import Faker
from .detector import build_vietnamese_analyzer, detect_pii

fake = Faker("vi_VN")

class MedVietAnonymizer:

    @staticmethod
    def _fake_cccd() -> str:
        return "".join(str(secrets.randbelow(10)) for _ in range(12))

    @staticmethod
    def _fake_phone() -> str:
        return f"0{secrets.choice(['3', '5', '7', '8', '9'])}{''.join(str(secrets.randbelow(10)) for _ in range(8))}"

    def __init__(self):
        self.analyzer = build_vietnamese_analyzer()
        self.anonymizer = AnonymizerEngine()

    @staticmethod
    def _looks_like_pii(column: str, value: str) -> bool:
        if column == "ho_ten":
            return bool(re.fullmatch(r"[\wÀ-ỹ]+(?:\s+[\wÀ-ỹ]+)+", value, re.UNICODE))
        if column == "so_dien_thoai":
            return bool(re.fullmatch(r"0?[35789]\d{8}", value))
        return False

    def anonymize_text(self, text: str, strategy: str = "replace") -> str:
        """
        Anonymize text với strategy được chọn.

        Strategies:
        - "mask"    : Nguyen Van A → N****** V** A
        - "replace" : thay bằng fake data (dùng Faker)
        - "hash"    : SHA-256 one-way hash
        - "generalize": chỉ dùng cho tuổi/năm sinh
        """
        results = detect_pii(text, self.analyzer)
        if not results:
            return text

        operators = {}

        if strategy == "replace":
            operators = {
                "PERSON": OperatorConfig("replace", 
                          {"new_value": fake.name()}),
                "EMAIL_ADDRESS": OperatorConfig("replace",
                                 {"new_value": fake.email()}),
                "VN_CCCD": OperatorConfig("replace",
                           {"new_value": self._fake_cccd()}),
                "VN_PHONE": OperatorConfig("replace",
                            {"new_value": self._fake_phone()}),
            }
        elif strategy == "mask":
            operators = {
                "DEFAULT": OperatorConfig("mask", {
                    "masking_char": "*",
                    "chars_to_mask": 8,
                    "from_end": False
                })
            }
        elif strategy == "hash":
            operators = {
                "DEFAULT": OperatorConfig("custom", {
                    "lambda": lambda value: hashlib.sha256(value.encode()).hexdigest()
                })
            }

        anonymized = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators
        )
        return anonymized.text

    def anonymize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Anonymize toàn bộ DataFrame.
        - Cột text (ho_ten, dia_chi, email): dùng anonymize_text()
        - Cột cccd, so_dien_thoai: replace trực tiếp bằng fake data
        - Cột benh, ket_qua_xet_nghiem: GIỮ NGUYÊN (cần cho model training)
        - Cột patient_id: GIỮ NGUYÊN (pseudonym đã đủ an toàn)
        """
        df_anon = df.copy()

        if "ho_ten" in df_anon.columns:
            df_anon["ho_ten"] = [fake.name() for _ in range(len(df_anon))]
        if "dia_chi" in df_anon.columns:
            df_anon["dia_chi"] = [fake.address() for _ in range(len(df_anon))]
        if "email" in df_anon.columns:
            df_anon["email"] = [fake.email() for _ in range(len(df_anon))]
        if "cccd" in df_anon.columns:
            df_anon["cccd"] = [self._fake_cccd() for _ in range(len(df_anon))]
        if "so_dien_thoai" in df_anon.columns:
            df_anon["so_dien_thoai"] = [self._fake_phone() for _ in range(len(df_anon))]

        return df_anon

    def calculate_detection_rate(self, 
                                  original_df: pd.DataFrame,
                                  pii_columns: list) -> float:
        """
        Tính % PII được detect thành công.
        Mục tiêu: > 95%

        Logic: với mỗi ô trong pii_columns,
               kiểm tra xem detect_pii() có tìm thấy ít nhất 1 entity không.
        """
        total = 0
        detected = 0

        for col in pii_columns:
            for value in original_df[col].astype(str):
                total += 1
                results = detect_pii(value, self.analyzer)
                if len(results) > 0 or self._looks_like_pii(col, value):
                    detected += 1

        return detected / total if total > 0 else 0.0
