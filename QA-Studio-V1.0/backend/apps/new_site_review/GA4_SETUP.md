# GA4 Property ID and OAuth Setup (New Site Review)

This app uses **OAuth only** (no Service Account). You sign in with Google once; the app then fetches Search Console (clicks, impressions) and GA4 (sessions) data and exports an Excel file when you click **Play** on a site.

**Required environment variables** (for OAuth):
- `GOOGLE_CLIENT_ID` – from Google Cloud Console (OAuth 2.0 Client ID)
- `GOOGLE_CLIENT_SECRET` – from the same client
- `APP_BASE_URL` – e.g. `http://localhost:8001` (used as redirect base)

This guide explains how to get your **GA4 Property ID** and how to set up OAuth.

---

## 1. How to Get Your GA4 Property ID

The **GA4 Property ID** is a numeric ID (8 or more digits) that identifies your Google Analytics 4 property. It is **not** the same as the Measurement ID (e.g. `G-XXXXXXXXXX`).

### Steps

1. **Open Google Analytics**  
   Go to [analytics.google.com](https://analytics.google.com) and sign in.

2. **Select the correct account and property**  
   Use the account/property selector in the top-left (or **Admin** → choose Account and Property).

3. **Open Admin**  
   Click the **gear icon** (Admin) in the bottom-left.

4. **Find Property ID**  
   - In the **Property** column, click **Property settings**.
   - The **Property ID** is shown near the top (e.g. `123456789`).  
   - Copy this number; this is your **GA4 Property ID** for this app.

### Format

- **Correct:** `123456789`, `412345678` (numeric only, typically 8–10 digits).
- **Not the same as:** Measurement ID (`G-XXXXXXXXXX`) or Universal Analytics ID (`UA-XXXXX-X`).

Use the numeric **Property ID** in New Site Review Settings.

---

## 2. OAuth vs Service Account

You need credentials so the app can call the **Google Analytics Data API** (e.g. to fetch metrics for a site). Two options are supported.

| | **OAuth** | **Service Account** |
|---|-----------|----------------------|
| **What it is** | User signs in with a Google account; Google issues short-lived tokens. | A robot account (JSON key) that can act without a user present. |
| **Best for** | Interactive use, single user, or when you want “sign in with Google”. | Servers, automation, scripts, and when no user is at the keyboard. |
| **Setup** | Configure OAuth consent + client ID/secret in Google Cloud Console; user signs in in browser. | Create a service account, download JSON key, grant it access in GA4. |
| **Security** | Tokens expire; user can revoke access. | Key file is long-lived; must be stored securely and not shared. |
| **In this app** | Choose **OAuth** in Settings when you will sign in yourself. | Choose **Service Account** and paste the JSON key content when running on a server or without a browser. |

---

## 3. OAuth (User sign-in)

### How it works

1. You (or the app) open a Google sign-in page.
2. You approve access to Analytics (scopes requested by the app).
3. Google returns tokens (access + refresh) that the app uses to call the API.
4. When the access token expires, the app uses the refresh token to get a new one (if implemented).

### When to use

- You are the only user, or a small team, and can sign in in a browser.
- You prefer not to manage a JSON key file.
- The app runs in an environment where a browser or redirect flow is possible.

### What you need (for developers)

- A **Google Cloud project** with the **Google Analytics Data API** enabled.
- **OAuth 2.0 Client ID** (e.g. “Web application” or “Desktop”) from **APIs & Services → Credentials**.
- **OAuth consent screen** configured (e.g. “Testing” or “Production”) with the right scopes (e.g. `https://www.googleapis.com/auth/analytics.readonly`).

In **New Site Review**, select **OAuth** in GA4 Settings and enter your **GA4 Property ID**. The app may prompt you to sign in when it needs to call the API (if the app implements the OAuth flow).

---

## 4. Service Account (no user sign-in)

### How it works

1. In Google Cloud Console you create a **Service Account** and download a **JSON key file**.
2. The JSON contains a private key and client email (e.g. `something@project-id.iam.gserviceaccount.com`).
3. The app uses this key to obtain access tokens itself—no browser or user sign-in.
4. The service account must be **granted access** to the GA4 property (see below).

### When to use

- The app runs on a **server** or in **automation** (e.g. scheduled jobs).
- You want **no interactive sign-in** (headless, scripts, CI).
- You are comfortable storing the JSON key securely (env var, secret manager, or encrypted config).

### Step-by-step: Create and use a Service Account

1. **Google Cloud Console**  
   Go to [console.cloud.google.com](https://console.cloud.google.com) and select (or create) the project linked to your GA4 property.

2. **Enable the API**  
   - **APIs & Services → Library**  
   - Search for **Google Analytics Data API**  
   - Open it and click **Enable**

3. **Create a Service Account**  
   - **APIs & Services → Credentials**  
   - **Create credentials → Service account**  
   - Name it (e.g. “New Site Review GA4”) and finish.

4. **Create a key**  
   - Open the new service account → **Keys** tab  
   - **Add key → Create new key → JSON**  
   - Download the JSON file.  
   - **Keep this file secret;** do not commit it to git or expose it in the UI.

5. **Grant the service account access in GA4**  
   - In **Google Analytics**, go to **Admin** (gear icon).  
   - In the **Property** column, click **Property access management**.  
   - **Add users** (or “+” ).  
   - Enter the **service account email** (e.g. `new-site-review@your-project.iam.gserviceaccount.com`).  
   - Role: at least **Viewer** (or “Read & analyze”) so it can read reporting data.  
   - Save.

6. **Use in New Site Review**  
   - In **New Site Review → Settings → GA4**, set **Credentials type** to **Service Account**.  
   - Enter your **GA4 Property ID**.  
   - Paste the **entire contents** of the JSON key file into the **Service account JSON** field (or use whatever the app expects, e.g. base64).  
   - Save. The app will use this to call the Analytics Data API without a user sign-in.

---

## 5. Summary

| Goal | Action |
|------|--------|
| **Get Property ID** | Google Analytics → Admin → Property settings → copy the numeric **Property ID**. |
| **Use OAuth** | Configure OAuth client + consent in Cloud Console; in the app choose OAuth and enter Property ID; sign in when prompted. |
| **Use Service Account** | Create service account → download JSON key → add that email as a user in GA4 Property access → in the app choose Service Account, enter Property ID and paste JSON. |

For **server or automated use**, prefer **Service Account**. For **single-user or interactive use**, **OAuth** is an option if the app supports it.
