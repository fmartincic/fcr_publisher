# FCR & FIC Facebook Publisher ☕🤖

Automated daily Facebook page publisher for **Full Coffee Roast** and **Fluent In Coffee**.

This repository runs a zero-dependency Python script via **GitHub Actions** on a fixed daily schedule (9:15 AM ET / 13:15 UTC) at **$0 recurring cost**. It tracks published articles in `posted_history.json` and automatically commits updates back to the repository so articles are never duplicated.

---

## 🎯 Supported Sites

| Site | RSS Feed | WordPress REST API |
| :--- | :--- | :--- |
| **Full Coffee Roast** | `https://www.fullcoffeeroast.com/feed/` | `https://www.fullcoffeeroast.com/wp-json/wp/v2/posts` |
| **Fluent In Coffee** | `https://www.fluentincoffee.com/feed/` | `https://www.fluentincoffee.com/wp-json/wp/v2/posts` |

---

## ⚙️ How It Works

1. **Daily Trigger:** GitHub Actions runs `.github/workflows/daily_publisher.yml` daily at `13:15 UTC` (9:15 AM Eastern Time / 6:15 AM Pacific Time).
2. **Article Discovery:** Fetches the latest articles from RSS feeds. If candidate count is low, discovers older unposted articles from WordPress REST API archives.
3. **Deduplication:** Checks against `posted_history.json` (GUID and URL) to ensure only unpublished articles are selected.
4. **Publishing:** Formats post preview and publishes directly to Facebook Pages via Meta Graph API v20.0.
5. **State Persistence:** Automatically commits updated `posted_history.json` back to `main` using `[skip ci]`.

---

## 🔐 Required GitHub Secrets Setup

To enable automated posting, navigate to your repository settings:
**Settings ➔ Secrets and variables ➔ Actions ➔ New repository secret**

Add the following 4 secrets:

| Secret Name | Description |
| :--- | :--- |
| `FCR_PAGE_ID` | Facebook Page ID for Full Coffee Roast |
| `FCR_PAGE_ACCESS_TOKEN` | Long-lived / Never-expiring Page Access Token for Full Coffee Roast |
| `FIC_PAGE_ID` | Facebook Page ID for Fluent In Coffee |
| `FIC_PAGE_ACCESS_TOKEN` | Long-lived / Never-expiring Page Access Token for Fluent In Coffee |

*Note:* Repository write access for updating `posted_history.json` is handled automatically via `secrets.GITHUB_TOKEN`. Ensure in **Settings ➔ Actions ➔ General ➔ Workflow permissions** that **"Read and write permissions"** is selected.

---

## 🚀 Manual Execution & Testing

### 1. Manual Trigger from GitHub UI
1. Navigate to the **Actions** tab in GitHub.
2. Select **Daily Facebook Publisher** from the left sidebar.
3. Click **Run workflow**.
4. Check **"Simulate without posting to Facebook"** (`dry_run`) to test without publishing, or leave unchecked to publish live.

### 2. Local Testing
Run the publisher locally using dry-run mode (no Facebook credentials required):

```bash
# Run dry-run simulation
python3 publish_to_fb.py --dry-run

# Run unit tests
python3 -m unittest discover tests -v
```

For live local execution, create a `.env` file (which is gitignored):
```env
FCR_PAGE_ID=your_fcr_page_id
FCR_PAGE_ACCESS_TOKEN=your_fcr_token
FIC_PAGE_ID=your_fic_page_id
FIC_PAGE_ACCESS_TOKEN=your_fic_token
```
Then run:
```bash
python3 publish_to_fb.py
```
