class settings:
    DB_HOST = ""
    DB_USER = ""
    DB_PASSWORD = ""
    DB_NAME = ""
    GROQ_API_KEY = ""
    EMBEDDING_API_URL = ""

    # Source DB  (sinterface — live call logs)
    SOURCE_DB_HOST     = ""
    SOURCE_DB_USER     = ""
    SOURCE_DB_PASSWORD = ""
    SOURCE_DB_NAME     = ""

    # Cluster DB  (test_ai — product hierarchy / reasons)
    CLUSTER_DB_HOST     = ""
    CLUSTER_DB_USER     = ""
    CLUSTER_DB_PASSWORD = ""
    CLUSTER_DB_NAME     = ""

    # AWS / SQS
    AWS_ACCESS_KEY_ID     = ""
    AWS_SECRET_ACCESS_KEY = ""
    SQS_QUEUE_GENERAL = ""
    SQS_QUEUE_VODA    = ""