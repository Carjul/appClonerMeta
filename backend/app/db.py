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
fb_catalogs_col = db["fb_catalogs"]
fb_products_col = db["fb_products"]
fb_product_sets_col = db["fb_product_sets"]
fb_campaign_templates_col = db["fb_campaign_templates"]
fb_campaigns_col = db["fb_campaigns"]
fb_media_assets_col = db["fb_media_assets"]
fb_language_carnadas_col = db["fb_language_carnadas"]
fb_copy_bundles_col = db["fb_copy_bundles"]
fb_planned_campaigns_col = db["fb_planned_campaigns"]

configs_col.create_index("name", unique=True)
job_logs_col.create_index([("job_id", 1), ("timestamp", 1)])
jobs_col.create_index("created_at")
daily_reports_col.create_index([("config_id", 1), ("generated_at", -1)])
rules_col.create_index([("config_id", 1), ("created_at", -1)])
rules_col.create_index("meta_rule_id")
rules_logs_col.create_index([("config_id", 1), ("timestamp", -1)])
fb_catalogs_col.create_index([("config_id", 1), ("created_at", -1)])
fb_catalogs_col.create_index("feed_slug", unique=True)
fb_products_col.create_index([("catalog_id", 1), ("created_at", 1)])
fb_products_col.create_index([("catalog_id", 1), ("retailer_id", 1)])
fb_product_sets_col.create_index([("catalog_id", 1), ("created_at", -1)])
fb_campaign_templates_col.create_index([("config_id", 1), ("created_at", -1)])
fb_campaigns_col.create_index([("config_id", 1), ("created_at", -1)])
fb_media_assets_col.create_index([("config_id", 1), ("created_at", -1)])
fb_language_carnadas_col.create_index([("config_id", 1), ("created_at", -1)])
fb_copy_bundles_col.create_index([("config_id", 1), ("created_at", -1)])
fb_planned_campaigns_col.create_index([("config_id", 1), ("created_at", -1)])
fb_planned_campaigns_col.create_index([("config_id", 1), ("status", 1)])
fb_planned_campaigns_col.create_index([("status", 1), ("scheduled_at", 1)])
