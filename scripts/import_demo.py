from __future__ import annotations

from pathlib import Path

from app.db import engine, SessionLocal, Base
from app.services.import_excel import import_wide_month_sheet

EXCEL_PATH = Path("data/demo/husky_kennel.xlsx")

def main():
    # Create tables if not exist
    Base.metadata.create_all(bind=engine)

    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel file not found: {EXCEL_PATH.resolve()}")

    sheet_name = "tracking_2025-12"
    source_label = f"{EXCEL_PATH.name}:{sheet_name}"

    with SessionLocal() as session:
        res = import_wide_month_sheet(
            session=session,
            excel_path=EXCEL_PATH,
            sheet_name=sheet_name,
            source_label=source_label,
            treat_zero_as_missing=False,
        )
        session.commit()

    print("✅ Import done")
    print(f"Dogs created: {res.dogs_created}")
    print(f"Rows inserted: {res.rows_inserted}")
    print(f"Rows skipped (duplicates): {res.rows_skipped_duplicates}")

if __name__ == "__main__":
    main()
