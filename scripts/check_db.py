from sqlalchemy import select, func
from app.db import SessionLocal
from app.models import Dog, TrainingLog

def main():
    with SessionLocal() as s:
        dogs = s.execute(select(func.count(Dog.id))).scalar_one()
        rows = s.execute(select(func.count(TrainingLog.id))).scalar_one()
        total_km = s.execute(select(func.sum(TrainingLog.distance_km))).scalar_one() or 0

        print(f"Dogs: {dogs}")
        print(f"Training rows: {rows}")
        print(f"Total km: {total_km:.1f}")

if __name__ == "__main__":
    main()
