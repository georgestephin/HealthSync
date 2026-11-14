import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SEED_DEMO_DATA = os.environ.get("SEED_DEMO_DATA", "1") == "1"  # demo users and sample data on an empty database
    BOOKING_WINDOW_DAYS = 90   # how far ahead patients can book
    CLAIMS_API_URL = os.environ.get("CLAIMS_API_URL", "http://localhost:3001/api/v1")   # the separate Claims service
    CLAIMS_ID_OFFSET = int(os.environ.get("CLAIMS_ID_OFFSET", "100000"))                # keeps our ids apart from other systems using the same claims database
    CLAIMS_TIMEOUT = 8                                                                 # seconds to wait for the Claims service
    QUEUE_DEFAULT_MINUTES = 10 # assumed consultation length until real timings exist
