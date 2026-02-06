# Roadmap

## Implemented (Current Demo)

- Rule-based workload analysis
- Kennel-level and dog-level dashboards
- Heatmaps and workload summaries
- Explainable risk indicators
- Team builder for daily sled planning
- Manual data input and Excel import
- Report and data export

This baseline version works without machine learning and can be used immediately.

---

## Possible Improvements

- Persistent database storage (PostgreSQL)
- Multi-kennel support
- User roles and access control
- Improved UI/UX (migration from Streamlit to Angular)
- Automated backups and reporting
- Better configuration management for workload rules

---

## Research & Machine Learning Extensions

Machine learning is treated as an **extension**, not a prerequisite.

### Phase 1 – Assisted Risk Scoring
- Logistic Regression or Gradient Boosting models
- Input features:
  - Recent work/rest patterns
  - Rolling workload windows
  - Age and role (optional)
- Output:
  - Risk score (0–1)
- Focus on explainability (coefficients, feature importance)

### Phase 2 – Comparative Evaluation
- Compare ML-based risk scores with rule-based baseline
- Validate results against operational observations
- Use ranking-based evaluation instead of injury prediction

### Phase 3 – Sensor-Based Research (Optional)
- Integration of activity trackers with API access
- Comparison of sensor data vs manual records
- Assessment of added value, cost, and feasibility
- Conducted during training season as a controlled experiment

The goal is not full automation, but **better decision support based on data quality and transparency**.
