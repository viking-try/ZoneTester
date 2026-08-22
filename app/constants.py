"""Enums shared across the app. Plain string constants (not Python Enum) so they serialize
directly into JSON/JSONB and SQL params without extra handling."""

SCANNABLE_RTYPES = {"A", "AAAA", "CNAME", "ALIAS"}


class RecordState:
    UNSCANNED = "unscanned"
    UP = "up"
    DOWN = "down"
    VALIDATION = "validation"
    ERROR = "error"


class ScanState:
    PENDING = "pending"
    QUEUED = "queued"
    SCANNING = "scanning"
    SCANNED = "scanned"
    FAILED = "failed"


class DownReason:
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    SSL_ERROR = "ssl_error"
    NO_ANSWER = "no_answer"


class CleanupAction:
    DELETE = "delete"
    INVESTIGATE = "investigate"
    KEEP = "keep"


class Role:
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"

    ORDER = {VIEWER: 0, OPERATOR: 1, ADMIN: 2}

    @classmethod
    def at_least(cls, actual: str, required: str) -> bool:
        return cls.ORDER.get(actual, -1) >= cls.ORDER.get(required, 99)


class JobState:
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class JobType:
    SCAN_RECORD = "scan_record"
    SCAN_BATCH = "scan_batch"
    SCAN_DOMAIN = "scan_domain"
    SEND_REPORT = "send_report"
    CREATE_TICKETS = "create_tickets"
    RETENTION_PRUNE = "retention_prune"
    RECONCILE_STUCK_JOBS = "reconcile_stuck_jobs"
    DAILY_SNAPSHOT = "daily_snapshot"


class ScanScope:
    ALL = "all"
    DOWN_ONLY = "down_only"
    UNSCANNED_ONLY = "unscanned_only"
    TLS12_ONLY = "tls12_only"


class EventType:
    NEW_DANGLING = "new_dangling"
    NEWLY_DOWN = "newly_down"
    NEW_WEAK_CIPHER = "new_weak_cipher"
    NEWLY_NOT_PQC = "newly_not_pqc"
    GRADE_REGRESSION = "grade_regression"
    CERT_EXPIRING_30D = "cert_expiring_30d"


class BatchFormat:
    ENRICHED_CSV = "enriched_csv"
    BARE_CSV = "bare_csv"
    BIND_ZONE = "bind_zone"
    ROUTE53_JSON = "route53_json"
