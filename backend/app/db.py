from pymongo import MongoClient
from app.config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

configs_col = db["configs"]
jobs_col = db["jobs"]
job_logs_col = db["job_logs"]
daily_reports_col = db["daily_reports"]
rules_col = db["rules"]
rules_logs_col = db["rules_logs"]

configs_col.create_index("name", unique=True)
job_logs_col.create_index([("job_id", 1), ("timestamp", 1)])
jobs_col.create_index("created_at")
daily_reports_col.create_index([("config_id", 1), ("generated_at", -1)])
rules_col.create_index([("config_id", 1), ("created_at", -1)])
rules_col.create_index("meta_rule_id")
rules_logs_col.create_index([("config_id", 1), ("timestamp", -1)])
