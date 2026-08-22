"""Known cloud-provider CNAME target patterns whose parent service is commonly torn down
without the DNS record being cleaned up — the classic subdomain-takeover setup. Matching a
pattern is a signal, not a verdict; confidence.py combines it with liveness history."""
import re

DEAD_TARGET_PATTERNS: list[tuple[str, str]] = [
    (r"\.cloudfront\.net$", "cloudfront"),
    (r"\.elb\.amazonaws\.com$", "elb"),
    (r"\.execute-api\.[a-z0-9-]+\.amazonaws\.com$", "api_gateway"),
    (r"\.s3-website[.-][a-z0-9-]+\.amazonaws\.com$", "s3_website"),
    (r"\.s3\.amazonaws\.com$", "s3_bucket"),
    (r"\.s3\.[a-z0-9-]+\.amazonaws\.com$", "s3_bucket"),
    (r"\.azurewebsites\.net$", "azure_app_service"),
    (r"\.trafficmanager\.net$", "azure_traffic_manager"),
    (r"\.azurefd\.net$", "azure_front_door"),
    (r"\.cloudapp\.azure\.com$", "azure_cloud_service"),
    (r"\.edgekey\.net$", "akamai"),
    (r"\.edgesuite\.net$", "akamai"),
    (r"\.akamaiedge\.net$", "akamai"),
    (r"\.herokuapp\.com$", "heroku"),
    (r"\.github\.io$", "github_pages"),
    (r"\.fastly\.net$", "fastly"),
]


def match_fingerprint(target: str) -> str | None:
    target = target.lower().rstrip(".")
    for pattern, name in DEAD_TARGET_PATTERNS:
        if re.search(pattern, target):
            return name
    return None
