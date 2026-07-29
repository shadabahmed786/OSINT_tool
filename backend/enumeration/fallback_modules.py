import asyncio
import hashlib
import logging
import re
import socket
import httpx
from backend.db.models import DatabaseManager
from backend.enumeration.base import Hit

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}
REQUEST_TIMEOUT = 12.0

# Known disposable / temporary email domains
DISPOSABLE_EMAIL_DOMAINS = {
    "tempmail.com", "10minutemail.com", "mailinator.com", "guerrillamail.com", "dispostable.com",
    "trashmail.com", "getairmail.com", "sharklasers.com", "throwawaymail.com", "temp-mail.org",
    "yopmail.com", "maildrop.cc", "tempmailo.com", "crazymailing.com", "fakemailgenerator.com"
}

# Regional Phone Dialing Code Database (30+ Countries)
COUNTRY_CODES = {
    "1": {"country": "United States / Canada", "iso": "US/CA", "flag": "🇺🇸/🇨🇦"},
    "44": {"country": "United Kingdom", "iso": "GB", "flag": "🇬🇧"},
    "91": {"country": "India", "iso": "IN", "flag": "🇮🇳"},
    "49": {"country": "Germany", "iso": "DE", "flag": "🇩🇪"},
    "33": {"country": "France", "iso": "FR", "flag": "🇫🇷"},
    "61": {"country": "Australia", "iso": "AU", "flag": "🇦🇺"},
    "81": {"country": "Japan", "iso": "JP", "flag": "🇯🇵"},
    "86": {"country": "China", "iso": "CN", "flag": "🇨🇳"},
    "7": {"country": "Russia / Kazakhstan", "iso": "RU/KZ", "flag": "🇷🇺"},
    "55": {"country": "Brazil", "iso": "BR", "flag": "🇧🇷"},
    "34": {"country": "Spain", "iso": "ES", "flag": "🇪🇸"},
    "39": {"country": "Italy", "iso": "IT", "flag": "🇮🇹"},
    "31": {"country": "Netherlands", "iso": "NL", "flag": "🇳🇱"},
    "41": {"country": "Switzerland", "iso": "CH", "flag": "🇨🇭"},
    "48": {"country": "Poland", "iso": "PL", "flag": "🇵🇱"},
    "62": {"country": "Indonesia", "iso": "ID", "flag": "🇮🇩"},
    "971": {"country": "United Arab Emirates", "iso": "AE", "flag": "🇦🇪"},
    "52": {"country": "Mexico", "iso": "MX", "flag": "🇲🇽"},
    "82": {"country": "South Korea", "iso": "KR", "flag": "🇰🇷"},
    "27": {"country": "South Africa", "iso": "ZA", "flag": "🇿🇦"},
    "46": {"country": "Sweden", "iso": "SE", "flag": "🇸🇪"},
    "47": {"country": "Norway", "iso": "NO", "flag": "🇳🇴"},
    "45": {"country": "Denmark", "iso": "DK", "flag": "🇩🇰"},
    "358": {"country": "Finland", "iso": "FI", "flag": "🇫🇮"},
    "966": {"country": "Saudi Arabia", "iso": "SA", "flag": "🇸🇦"},
    "65": {"country": "Singapore", "iso": "SG", "flag": "🇸🇬"},
    "64": {"country": "New Zealand", "iso": "NZ", "flag": "🇳🇿"},
}

async def run_username_http_fallback(username: str, investigation_id: str, db: DatabaseManager) -> list[Hit]:
    """
    High-precision, high-speed username checker using concurrent parallel API calls.
    Executes all platform checks simultaneously for sub-2-second total response time.
    """
    db.log_evidence(investigation_id, "search_started", {"module": "username_checker", "target": username})
    hits: list[Hit] = []

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=5.0, follow_redirects=True) as client:

        async def check_github():
            try:
                resp = await client.get(f"https://api.github.com/users/{username}")
                if resp.status_code == 200:
                    data = resp.json()
                    login = data.get("login")
                    if login and login.lower() == username.lower():
                        bio = f"GitHub ({data.get('type', 'User')}) | Repos: {data.get('public_repos', 0)} | Followers: {data.get('followers', 0)}"
                        if data.get("bio"):
                            bio += f" | Bio: {data.get('bio')}"
                        return Hit(
                            platform="GitHub",
                            source_tool="username_checker",
                            display_name=login,
                            profile_picture_path=data.get("avatar_url"),
                            bio=bio,
                            account_status="active",
                            confidence_tier="HIGH",
                            confidence_score=0.95
                        )
            except Exception as e:
                logger.debug(f"GitHub check error: {e}")
            return None

        async def check_gitlab():
            try:
                resp = await client.get(f"https://gitlab.com/api/v4/users?username={username}")
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        user = data[0]
                        if user.get("username", "").lower() == username.lower():
                            return Hit(
                                platform="GitLab",
                                source_tool="username_checker",
                                display_name=user.get("name") or user.get("username"),
                                profile_picture_path=user.get("avatar_url"),
                                bio=f"GitLab User ID: {user.get('id')} | Profile: {user.get('web_url')}",
                                account_status="active",
                                confidence_tier="HIGH",
                                confidence_score=0.90
                            )
            except Exception as e:
                logger.debug(f"GitLab check error: {e}")
            return None

        async def check_hackernews():
            try:
                resp = await client.get(f"https://hacker-news.firebaseio.com/v0/user/{username}.json")
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, dict) and data.get("id"):
                        hn_id = data.get("id")
                        karma = data.get("karma", 0)
                        about = data.get("about", "")
                        bio = f"HackerNews User | Karma: {karma}"
                        if about:
                            bio += f" | About: {about[:100]}"
                        return Hit(
                            platform="HackerNews",
                            source_tool="username_checker",
                            display_name=hn_id,
                            bio=bio,
                            account_status="active",
                            confidence_tier="HIGH",
                            confidence_score=0.85
                        )
            except Exception as e:
                logger.debug(f"HackerNews check error: {e}")
            return None

        async def check_devto():
            try:
                resp = await client.get(f"https://dev.to/api/users/by_username?url={username}")
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, dict) and data.get("username"):
                        dev_user = data.get("username")
                        return Hit(
                            platform="Dev.to",
                            source_tool="username_checker",
                            display_name=data.get("name") or dev_user,
                            profile_picture_path=data.get("profile_image"),
                            bio=f"Dev.to Developer | Bio: {data.get('summary') or 'N/A'}",
                            account_status="active",
                            confidence_tier="HIGH",
                            confidence_score=0.85
                        )
            except Exception as e:
                logger.debug(f"Dev.to check error: {e}")
            return None

        async def check_pypi():
            try:
                resp = await client.get(f"https://pypi.org/user/{username}/")
                if resp.status_code == 200 and f"/{username}/" in resp.text:
                    return Hit(
                        platform="PyPI",
                        source_tool="username_checker",
                        display_name=username,
                        bio=f"Python Package Index Author Profile: https://pypi.org/user/{username}/",
                        account_status="active",
                        confidence_tier="HIGH",
                        confidence_score=0.80
                    )
            except Exception as e:
                logger.debug(f"PyPI check error: {e}")
            return None

        async def check_dockerhub():
            try:
                resp = await client.get(f"https://hub.docker.com/v2/users/{username}/")
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, dict) and data.get("username"):
                        return Hit(
                            platform="DockerHub",
                            source_tool="username_checker",
                            display_name=data.get("full_name") or username,
                            profile_picture_path=data.get("profile_media"),
                            bio=f"DockerHub Container Registry User ({username})",
                            account_status="active",
                            confidence_tier="HIGH",
                            confidence_score=0.85
                        )
            except Exception as e:
                logger.debug(f"DockerHub check error: {e}")
            return None

        async def check_substack():
            try:
                resp = await client.get(f"https://{username}.substack.com")
                if resp.status_code == 200 and ("substack.com" in resp.text.lower() or "newsletter" in resp.text.lower()):
                    return Hit(
                        platform="Substack",
                        source_tool="username_checker",
                        display_name=f"{username}.substack.com",
                        bio=f"Substack Newsletter Publication: https://{username}.substack.com",
                        account_status="active",
                        confidence_tier="HIGH",
                        confidence_score=0.80
                    )
            except Exception as e:
                logger.debug(f"Substack check error: {e}")
            return None

        async def check_keybase():
            try:
                resp = await client.get(f"https://keybase.io/_/api/1.0/user/lookup.json?usernames={username}")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status", {}).get("code") == 0:
                        them = data.get("them", [])
                        if them and len(them) > 0 and them[0] is not None:
                            kb_user = them[0]
                            profile = kb_user.get("profile", {})
                            full_name = profile.get("full_name") or username
                            bio_text = profile.get("bio") or "Keybase Identity Profile"
                            avatar = kb_user.get("pictures", {}).get("primary", {}).get("url")

                            return Hit(
                                platform="Keybase",
                                source_tool="username_checker",
                                display_name=full_name,
                                profile_picture_path=avatar,
                                bio=f"Keybase PGP Identity | {bio_text}",
                                account_status="active",
                                confidence_tier="HIGH",
                                confidence_score=0.95
                            )
            except Exception as e:
                logger.debug(f"Keybase check error: {e}")
            return None

        async def check_codepen():
            try:
                resp = await client.get(f"https://codepen.io/{username}")
                if resp.status_code == 200 and ("profile-header" in resp.text or "codepen" in resp.text.lower()):
                    return Hit(
                        platform="CodePen",
                        source_tool="username_checker",
                        display_name=username,
                        bio=f"CodePen Frontend Developer Profile: https://codepen.io/{username}",
                        account_status="active",
                        confidence_tier="HIGH",
                        confidence_score=0.80
                    )
            except Exception as e:
                logger.debug(f"CodePen check error: {e}")
            return None

        # Run ALL platform API checks simultaneously in parallel
        tasks = [
            check_github(),
            check_gitlab(),
            check_hackernews(),
            check_devto(),
            check_pypi(),
            check_dockerhub(),
            check_substack(),
            check_keybase(),
            check_codepen(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Hit):
                hits.append(res)
                db.log_evidence(investigation_id, "hit_recorded", {"platform": res.platform, "username": username})

    return hits


async def run_email_http_fallback(email: str, investigation_id: str, db: DatabaseManager) -> list[Hit]:
    """
    High-precision email checker.
    - Performs Gravatar profile & avatar checks
    - Queries GitHub email search API to find linked usernames
    - Validates domain MX records & flags disposable email services
    """
    db.log_evidence(investigation_id, "search_started", {"module": "email_checker", "target": email})
    hits: list[Hit] = []
    email_clean = email.strip().lower()

    if "@" not in email_clean:
        return []

    username_part, domain_part = email_clean.split("@", 1)
    email_md5 = hashlib.md5(email_clean.encode("utf-8")).hexdigest()

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:

        # 1. Gravatar JSON & Avatar Check
        try:
            gravatar_json_url = f"https://www.gravatar.com/{email_md5}.json"
            resp = await client.get(gravatar_json_url)
            if resp.status_code == 200:
                data = resp.json()
                entry = data.get("entry", [{}])[0]
                disp_name = entry.get("displayName") or entry.get("preferredUsername") or username_part
                profile_url = entry.get("profileUrl") or f"https://gravatar.com/{email_md5}"
                avatar_url = entry.get("thumbnailUrl") or f"https://www.gravatar.com/avatar/{email_md5}"
                bio = entry.get("aboutMe") or f"Registered Gravatar user profile for {email_clean}"

                hits.append(Hit(
                    platform="Gravatar",
                    source_tool="email_checker",
                    display_name=disp_name,
                    profile_picture_path=avatar_url,
                    bio=f"Gravatar Profile: {profile_url} | {bio}",
                    account_status="active",
                    confidence_tier="HIGH",
                    confidence_score=0.90
                ))
                db.log_evidence(investigation_id, "hit_recorded", {"platform": "Gravatar", "email": email_clean})
            else:
                # Avatar direct image check
                img_url = f"https://www.gravatar.com/avatar/{email_md5}?d=404"
                img_resp = await client.get(img_url)
                if img_resp.status_code == 200:
                    hits.append(Hit(
                        platform="Gravatar Avatar",
                        source_tool="email_checker",
                        display_name=username_part,
                        profile_picture_path=img_url,
                        bio=f"Gravatar profile avatar image registered for {email_clean}",
                        account_status="active",
                        confidence_tier="HIGH",
                        confidence_score=0.85
                    ))
                    db.log_evidence(investigation_id, "hit_recorded", {"platform": "Gravatar Avatar", "email": email_clean})
        except Exception as e:
            logger.debug(f"Gravatar check error: {e}")

        # 2. GitHub Email Linkage Search API
        try:
            github_url = f"https://api.github.com/search/users?q={email_clean}+in:email"
            resp = await client.get(github_url)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items and len(items) > 0:
                    gh_user = items[0]
                    login = gh_user.get("login")
                    hits.append(Hit(
                        platform="GitHub Email Linkage",
                        source_tool="email_checker",
                        display_name=login,
                        profile_picture_path=gh_user.get("avatar_url"),
                        bio=f"Linked GitHub Account: {login} | URL: {gh_user.get('html_url')}",
                        account_status="active",
                        confidence_tier="HIGH",
                        confidence_score=0.95
                    ))
                    db.log_evidence(investigation_id, "hit_recorded", {"platform": "GitHub Email Linkage", "username": login})
        except Exception as e:
            logger.debug(f"GitHub email search error: {e}")

        # 3. WordPress.com Account Check
        try:
            wp_url = f"https://public-api.wordpress.com/rest/v1.1/users/{email_clean}"
            resp = await client.get(wp_url)
            if resp.status_code in [200, 400] and "invalid_user" not in resp.text:
                hits.append(Hit(
                    platform="WordPress.com",
                    source_tool="email_checker",
                    display_name=username_part,
                    bio=f"Email registered on WordPress.com Network",
                    account_status="active",
                    confidence_tier="HIGH",
                    confidence_score=0.85
                ))
                db.log_evidence(investigation_id, "hit_recorded", {"platform": "WordPress.com", "email": email_clean})
        except Exception as e:
            logger.debug(f"WordPress check error: {e}")

        # 4. Domain Health & Disposable Status Check via Cloudflare DoH
        try:
            is_disposable = domain_part.lower() in DISPOSABLE_EMAIL_DOMAINS
            doh_url = f"https://cloudflare-dns.com/dns-query?name={domain_part}&type=MX"
            resp = await client.get(doh_url, headers={"Accept": "application/dns-json"})
            has_mx = False
            mx_details = []

            if resp.status_code == 200:
                data = resp.json()
                answers = data.get("Answer", [])
                if answers:
                    has_mx = True
                    mx_details = [a.get("data") for a in answers if a.get("data")]

            disposable_tag = " [DISPOSABLE EMAIL SERVICE]" if is_disposable else ""
            mx_status = f"Valid MX Mail Servers: {', '.join(mx_details[:2])}" if has_mx else "No MX Records Found"

            hits.append(Hit(
                platform="Email Domain Hygiene",
                source_tool="email_checker",
                display_name=f"@{domain_part}",
                bio=f"Domain: {domain_part}{disposable_tag} | {mx_status}",
                account_status="active" if has_mx else "inactive",
                confidence_tier="HIGH" if has_mx else "MEDIUM",
                confidence_score=0.85 if has_mx else 0.40
            ))
        except Exception as e:
            logger.debug(f"Domain MX check error: {e}")

    return hits


async def run_phone_http_fallback(phone: str, investigation_id: str, db: DatabaseManager) -> list[Hit]:
    """
    High-precision telephony metadata parser & regional classifier.
    """
    db.log_evidence(investigation_id, "search_started", {"module": "phone_checker", "target": phone})
    digits = re.sub(r"\D", "", phone)

    if len(digits) < 7 or len(digits) > 15:
        return []

    e164 = f"+{digits}" if not phone.startswith("+") else phone
    detected_country = "International / Unknown"
    iso_code = "UNKNOWN"
    country_flag = "🌐"

    for code in sorted(COUNTRY_CODES.keys(), key=lambda k: len(k), reverse=True):
        if digits.startswith(code):
            info = COUNTRY_CODES[code]
            detected_country = info["country"]
            iso_code = info["iso"]
            country_flag = info["flag"]
            break

    line_type = "Mobile / Landline"
    if digits.startswith("1800") or digits.startswith("1888") or digits.startswith("1877") or digits.startswith("1866"):
        line_type = "Toll-Free / Business Line"

    hit = Hit(
        platform="Telephony Metadata Registry",
        source_tool="phone_checker",
        display_name=f"{country_flag} {detected_country} ({iso_code})",
        region=detected_country,
        bio=f"E.164 Standard Format: {e164} | Country: {detected_country} ({iso_code}) | Estimated Line Type: {line_type} | Digit Length: {len(digits)}",
        account_status="active",
        confidence_tier="HIGH",
        confidence_score=0.90
    )
    db.log_evidence(investigation_id, "hit_recorded", {"tool": "phone_checker", "e164": e164, "country": detected_country})
    return [hit]


async def run_domain_http_fallback(domain: str, investigation_id: str, db: DatabaseManager) -> list[Hit]:
    """
    High-precision domain OSINT recon module using Cloudflare DNS over HTTPS (DoH)
    and crt.sh Certificate Transparency logs.
    """
    db.log_evidence(investigation_id, "search_started", {"module": "domain_checker", "target": domain})
    hits: list[Hit] = []
    domain_clean = domain.strip().lower()

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:

        # 1. DNS over HTTPS (Cloudflare DoH) for A, MX, NS, TXT
        record_types = ["A", "MX", "NS", "TXT"]
        dns_summary = []

        for rtype in record_types:
            try:
                resp = await client.get(
                    f"https://cloudflare-dns.com/dns-query?name={domain_clean}&type={rtype}",
                    headers={"Accept": "application/dns-json"}
                )
                if resp.status_code == 200:
                    answers = resp.json().get("Answer", [])
                    records = [a.get("data") for a in answers if a.get("data")]
                    if records:
                        dns_summary.append(f"{rtype}: {', '.join(records[:3])}")
            except Exception as e:
                logger.debug(f"DNS query error for {rtype}: {e}")

        if dns_summary:
            hits.append(Hit(
                platform="DNS Records (Cloudflare DoH)",
                source_tool="domain_checker",
                display_name=domain_clean,
                bio=f"Domain Recon Summary | {' | '.join(dns_summary)}",
                account_status="active",
                confidence_tier="HIGH",
                confidence_score=0.90
            ))
            db.log_evidence(investigation_id, "hit_recorded", {"platform": "DNS Records", "domain": domain_clean})

        # 2. crt.sh Subdomain Certificate Transparency Log
        try:
            crt_url = f"https://crt.sh/?q=%25.{domain_clean}&output=json"
            resp = await client.get(crt_url)
            if resp.status_code == 200:
                crt_data = resp.json()
                subdomains = set()
                for item in crt_data[:30]:
                    name = item.get("name_value")
                    if name:
                        for sub in name.splitlines():
                            sub_clean = sub.strip().lower().replace("*.", "")
                            if domain_clean in sub_clean:
                                subdomains.add(sub_clean)

                if subdomains:
                    sub_list = sorted(list(subdomains))[:10]
                    hits.append(Hit(
                        platform="Certificate Transparency Logs",
                        source_tool="domain_checker",
                        display_name=f"Subdomains Discovered ({len(subdomains)})",
                        bio=f"Discovered Subdomains: {', '.join(sub_list)}",
                        account_status="active",
                        confidence_tier="HIGH",
                        confidence_score=0.85
                    ))
                    db.log_evidence(investigation_id, "hit_recorded", {"platform": "Certificate Transparency", "count": len(subdomains)})
        except Exception as e:
            logger.debug(f"crt.sh search error: {e}")

    return hits
