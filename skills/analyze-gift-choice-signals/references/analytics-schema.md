# Aggregate analysis input schema

Read four SQLite tables: `sessions`, `final_requirements`, `recommendation_events`, and `selection_events`. Join only by anonymous session and recommendation IDs inside the service; never emit those IDs.

Supported filters are ISO date/time bounds, exact recipient, exact scene, budget bucket (`under_500`, `500_999`, `1000_1999`, `2000_plus`, `unknown`), and exact product ID.

`data_source` must remain `consented_user` or `synthetic_demo`. Any report containing the latter must display the synthetic-data notice.
