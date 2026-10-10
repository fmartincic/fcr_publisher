import os
import sys
import json
import random
import argparse
from datetime import datetime
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse
import urllib.error
import html
import re

# ==========================================
# CONFIGURATION
# ==========================================
SITES = [
    {
        "name": "Full Coffee Roast",
        "header_new": "☕ NEW ON FULL COFFEE ROAST ☕",
        "feed_url": "https://www.fullcoffeeroast.com/feed/",
        "wp_api_url": "https://www.fullcoffeeroast.com/wp-json/wp/v2/posts",
        "hashtags": "#FullCoffeeRoast #CoffeeLovers #CoffeeBrewing #CoffeeTips #HomeBarista",
        "env_page_id": "FCR_PAGE_ID",
        "env_token": "FCR_PAGE_ACCESS_TOKEN"
    },
    {
        "name": "Fluent In Coffee",
        "header_new": "☕ NEW ON FLUENT IN COFFEE ☕",
        "feed_url": "https://www.fluentincoffee.com/feed/",
        "wp_api_url": "https://www.fluentincoffee.com/wp-json/wp/v2/posts",
        "hashtags": "#FluentInCoffee #CoffeeLovers #CoffeeReview #CoffeeBrewing #Barista",
        "env_page_id": "FIC_PAGE_ID",
        "env_token": "FIC_PAGE_ACCESS_TOKEN"
    }
]

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "posted_history.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), ".env")
GRAPH_API_VERSION = "v20.0"

# ==========================================
# CONFIG & HISTORY HELPERS
# ==========================================
def load_config():
    """Load config from .env file and environment variables."""
    config = dict(os.environ)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    config[key.strip()] = val.strip().strip('"').strip("'")
    return config

def save_config(config):
    """Save updated config back to .env file."""
    lines = [
        "# ==========================================",
        "# FULL COFFEE ROAST CREDENTIALS",
        "# ==========================================",
        f"FCR_PAGE_ID={config.get('FCR_PAGE_ID', '')}",
        f"FCR_PAGE_ACCESS_TOKEN={config.get('FCR_PAGE_ACCESS_TOKEN', '')}",
        "",
        "# ==========================================",
        "# FLUENT IN COFFEE CREDENTIALS",
        "# ==========================================",
        f"FIC_PAGE_ID={config.get('FIC_PAGE_ID', '')}",
        f"FIC_PAGE_ACCESS_TOKEN={config.get('FIC_PAGE_ACCESS_TOKEN', '')}",
        ""
    ]
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def resolve_tokens_from_input(input_token, sites, config):
    """
    Resolve page tokens from a runtime token.
    Handles both User Tokens (auto-fetching page tokens for each site) and direct Page Tokens.
    """
    print("🔑 Resolving runtime token with Meta Graph API...", flush=True)
    resolved = {}
    
    # 1. Try querying each site's page ID directly with the token
    for site in sites:
        page_id = config.get(site["env_page_id"])
        if not page_id:
            continue
        try:
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}?fields=access_token,name&access_token={input_token}"
            req = urllib.request.Request(url, headers={"User-Agent": "CoffeeBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "access_token" in data:
                    resolved[site["name"]] = data["access_token"]
                    print(f"  ✅ Obtained Page Token for {site['name']} ({data.get('name')})", flush=True)
        except Exception:
            pass

    # 2. Try querying me/accounts as fallback for User Token
    if len(resolved) < len(sites):
        try:
            url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/accounts?fields=id,name,access_token&access_token={input_token}"
            req = urllib.request.Request(url, headers={"User-Agent": "CoffeeBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("data", []):
                    for site in sites:
                        if config.get(site["env_page_id"]) == item.get("id"):
                            resolved[site["name"]] = item["access_token"]
                            print(f"  ✅ Found Page Token in accounts for {site['name']}", flush=True)
        except Exception:
            pass

    # 3. If it didn't resolve as a user token, apply directly to all target pages
    if not resolved:
        print("  ℹ️ Token appears to be a direct Page Token. Applying to all target pages.", flush=True)
        for site in sites:
            resolved[site["name"]] = input_token

    return resolved

def load_history_data():
    """Load structured history data with backward compatibility."""
    default_data = {
        "posted_articles": [],
        "last_post_date": {}
    }
    if not os.path.exists(HISTORY_FILE):
        return default_data

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Upgrade from old flat list if needed
        if isinstance(raw, list):
            migrated = []
            for item in raw:
                migrated.append({
                    "guid": item,
                    "url": item,
                    "posted_at": "unknown",
                    "post_type": "legacy"
                })
            return {"posted_articles": migrated, "last_post_date": {}}

        if isinstance(raw, dict):
            return {
                "posted_articles": raw.get("posted_articles", []),
                "last_post_date": raw.get("last_post_date", {})
            }
    except Exception as e:
        print(f"⚠️ Warning loading history: {e}. Using empty history.", flush=True)

    return default_data

def save_history_data(history_data):
    """Save structured history data."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2)

def get_posted_identifiers(history_data):
    """Return a set of already posted GUIDs and URLs for quick lookup."""
    seen = set()
    for item in history_data.get("posted_articles", []):
        if "guid" in item and item["guid"]:
            seen.add(item["guid"].strip())
        if "url" in item and item["url"]:
            seen.add(item["url"].strip().rstrip("/"))
    return seen

def is_already_posted(article, posted_set):
    """Check if an article has already been posted to Facebook."""
    guid = article.get("guid", "").strip()
    link = article.get("link", "").strip().rstrip("/")
    return guid in posted_set or link in posted_set

# ==========================================
# CONTENT FETCHING
# ==========================================
def clean_html_text(text):
    """Strip HTML, markdown code tags, and cleanup whitespace."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'["“`\']*html\s*', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'["“`\']+', '', clean)
    clean = re.sub(r'Read more.*', '', clean, flags=re.IGNORECASE)
    clean = html.unescape(clean)
    return ' '.join(clean.split())

def fetch_feed_articles(feed_url):
    """Fetch latest articles from the RSS feed."""
    req = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CoffeeBot/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    articles = []

    for item in root.findall(".//item"):
        title = clean_html_text(item.findtext("title", default="").strip())
        link = item.findtext("link", default="").strip()
        guid = item.findtext("guid", default=link).strip()
        pub_date = item.findtext("pubDate", default="").strip()
        description = clean_html_text(item.findtext("description", default="").strip())

        articles.append({
            "title": title,
            "link": link,
            "guid": guid,
            "pub_date": pub_date,
            "description": description
        })

    return articles

def fetch_wp_api_backlog(wp_api_url, posted_set):
    """Fetch unposted articles from WordPress REST API using random pagination."""
    articles = []
    try:
        # Check total pages
        head_req = urllib.request.Request(
            f"{wp_api_url}?per_page=1",
            headers={"User-Agent": "Mozilla/5.0 (compatible; CoffeeBot/1.0)"}
        )
        with urllib.request.urlopen(head_req, timeout=15) as resp:
            total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))

        # Pick random page(s) to discover varied archive content
        max_page = min(total_pages, 40)
        pages_to_check = random.sample(range(1, max_page + 1), min(3, max_page))

        for page_num in pages_to_check:
            req = urllib.request.Request(
                f"{wp_api_url}?per_page=20&page={page_num}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; CoffeeBot/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                items = json.loads(resp.read().decode("utf-8"))
                for item in items:
                    title = clean_html_text(item.get("title", {}).get("rendered", ""))
                    link = item.get("link", "").strip()
                    post_id = str(item.get("id", ""))
                    guid = f"{link.split('.com')[0]}.com/?p={post_id}"
                    excerpt = clean_html_text(item.get("excerpt", {}).get("rendered", ""))
                    pub_date = item.get("date", "")

                    art = {
                        "title": title,
                        "link": link,
                        "guid": guid,
                        "pub_date": pub_date,
                        "description": excerpt
                    }
                    if not is_already_posted(art, posted_set):
                        articles.append(art)

    except Exception as e:
        print(f"⚠️ WP REST API backlog fetch notice: {e}", flush=True)

    return articles

# ==========================================
# POST FORMATTING
# ==========================================
def generate_facebook_post(site_config, article, is_backfill=False):
    """Generate Facebook post text. New posts include a header; backfills do not."""
    title = article["title"]
    link = article["link"]
    clean_desc = article.get("description", "")

    # Extract first 1-2 clean sentences
    summary = ""
    if clean_desc:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_desc) if s.strip()]
        if sentences:
            summary = " ".join(sentences[:2])

    hashtags = site_config["hashtags"]

    if is_backfill:
        post_text = f"""{title}

{summary if summary else "Check out our full guide and coffee tips on the blog!"}

👉 Read the full article here:
{link}

{hashtags}"""
    else:
        header = site_config["header_new"]
        post_text = f"""{header}

{title}

{summary if summary else "Check out our latest coffee guide and brewing tips on the blog!"}

👉 Read the full article here:
{link}

{hashtags}"""

    return post_text

# ==========================================
# FACEBOOK API PUBLISHING
# ==========================================
def post_to_facebook(page_id, page_access_token, message, link):
    """Publish a post to the Facebook Page via Meta Graph API."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}/feed"

    data = urllib.parse.urlencode({
        "message": message,
        "link": link,
        "access_token": page_access_token
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return True, result.get("id")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return False, f"HTTP {e.code}: {err_msg}"
    except Exception as e:
        return False, str(e)

# ==========================================
# MAIN ROUTINE
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Publish an unpublished article from each site to Facebook.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without posting to Facebook.")
    parser.add_argument("--token", "-t", type=str, default=None, help="New access token to use for publishing.")
    parser.add_argument("--fcr-token", type=str, default=None, help="Explicit token override for Full Coffee Roast.")
    parser.add_argument("--fic-token", type=str, default=None, help="Explicit token override for Fluent In Coffee.")
    parser.add_argument("--no-save", action="store_true", help="Do not save the runtime token to .env.")
    args = parser.parse_args()

    # Environment DRY_RUN flag support for CI workflow dispatch
    is_dry_run = args.dry_run or os.environ.get("DRY_RUN", "").lower() in ("true", "1", "yes")

    config = load_config()
    history_data = load_history_data()
    posted_set = get_posted_identifiers(history_data)
    timestamp_now = datetime.now().isoformat()
    config_modified = False

    # Handle explicit token overrides
    if args.fcr_token:
        config["FCR_PAGE_ACCESS_TOKEN"] = args.fcr_token
        config_modified = True
        print("🔑 Applied custom token for Full Coffee Roast.", flush=True)

    if args.fic_token:
        config["FIC_PAGE_ACCESS_TOKEN"] = args.fic_token
        config_modified = True
        print("🔑 Applied custom token for Fluent In Coffee.", flush=True)

    # Handle single unified token parameter (--token)
    if args.token:
        resolved_tokens = resolve_tokens_from_input(args.token.strip(), SITES, config)
        if "Full Coffee Roast" in resolved_tokens and not args.fcr_token:
            config["FCR_PAGE_ACCESS_TOKEN"] = resolved_tokens["Full Coffee Roast"]
            config_modified = True
        if "Fluent In Coffee" in resolved_tokens and not args.fic_token:
            config["FIC_PAGE_ACCESS_TOKEN"] = resolved_tokens["Fluent In Coffee"]
            config_modified = True

    # Save newly passed tokens to .env only if local .env exists or explicit save allowed
    if config_modified and not args.no_save and os.path.exists(CONFIG_FILE):
        save_config(config)
        print("💾 Updated .env file with new access token(s).", flush=True)

    print(f"==========================================", flush=True)
    print(f"🤖 Full Coffee Roast & Fluent In Coffee FB Publisher", flush=True)
    print(f"📅 Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Dry-run: {is_dry_run}", flush=True)
    print(f"==========================================", flush=True)

    has_fatal_error = False

    for site in SITES:
        site_name = site["name"]
        page_id = config.get(site["env_page_id"])
        page_token = config.get(site["env_token"])

        print(f"\n------------------------------------------", flush=True)
        print(f"🔍 Processing: {site_name}", flush=True)
        print(f"Target Page ID: {page_id or 'NOT_SET'}", flush=True)
        print(f"------------------------------------------", flush=True)

        if not is_dry_run and (not page_id or not page_token):
            print(f"❌ Missing credentials {site['env_page_id']} / {site['env_token']} in environment.", flush=True)
            has_fatal_error = True
            continue

        # 1. Fetch latest feed articles
        try:
            feed_articles = fetch_feed_articles(site["feed_url"])
            print(f"Fetched {len(feed_articles)} articles from RSS feed.", flush=True)
        except Exception as e:
            print(f"⚠️ Error fetching RSS feed: {e}", flush=True)
            feed_articles = []

        # Find unposted articles from feed
        candidates = [a for a in feed_articles if not is_already_posted(a, posted_set)]

        # If pool is small (like Full Coffee Roast's 5-item feed), expand from WordPress archive
        if len(candidates) < 10 and site.get("wp_api_url"):
            print(f"🔎 Expanding pool from WordPress archive...", flush=True)
            wp_candidates = fetch_wp_api_backlog(site["wp_api_url"], posted_set)
            candidates.extend(wp_candidates)

        # Deduplicate candidates
        unique_candidates = []
        seen_cand = set()
        for cand in candidates:
            key = cand["link"].rstrip("/")
            if key not in seen_cand and not is_already_posted(cand, posted_set):
                seen_cand.add(key)
                unique_candidates.append(cand)

        if not unique_candidates:
            print(f"✅ All available articles for {site_name} have already been posted!", flush=True)
            continue

        # Pick a random unpublished article
        article_to_post = random.choice(unique_candidates)
        print(f"🎲 Selected random unpublished article from pool of {len(unique_candidates)}: '{article_to_post['title']}'", flush=True)

        # Generate clean post without header
        post_text = generate_facebook_post(site, article_to_post, is_backfill=True)

        print("\n--- Generated Post Preview ---", flush=True)
        print(post_text, flush=True)
        print("------------------------------\n", flush=True)

        # Publish or Dry Run
        if is_dry_run:
            print(f"🧪 [DRY RUN] Would publish to Facebook Page {page_id}. No action taken.", flush=True)
        else:
            success, res = post_to_facebook(page_id, page_token, post_text, article_to_post["link"])
            if success:
                print(f"🎉 Successfully posted to Facebook! (Post ID: {res})", flush=True)

                # Record in history
                history_data["posted_articles"].append({
                    "site": site_name,
                    "title": article_to_post["title"],
                    "url": article_to_post["link"],
                    "guid": article_to_post["guid"],
                    "posted_at": timestamp_now,
                    "post_id": str(res),
                    "post_type": "automated"
                })
                history_data["last_post_date"][site_name] = datetime.now().strftime("%Y-%m-%d")
                save_history_data(history_data)
                posted_set.add(article_to_post["guid"])
                posted_set.add(article_to_post["link"].rstrip("/"))
            else:
                print(f"❌ Failed to post: {res}", flush=True)
                has_fatal_error = True

    print("\n🏁 Execution finished.", flush=True)
    if has_fatal_error:
        print("⚠️ Exiting with error status 1 due to failed postings or missing credentials.", flush=True)
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
