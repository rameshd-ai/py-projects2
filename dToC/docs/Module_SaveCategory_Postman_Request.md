# Module Creation API – Postman Request (SaveCategory)

Use this to test the **SaveCategory** API that creates module categories (e.g. "Our Resort"). The app sends this request when a page has no matching category.

---

## 1. URL

**Method:** `POST`

**Full URL:**
```
https://<YOUR_CMS_BASE_URL>/ccadmin/cms/api/ModuleApi/SaveCategory
```

**Example** (replace with your target_site_url from config):
```
https://tarrytownhouseestate.web4cms.milestoneinternet.info/ccadmin/cms/api/ModuleApi/SaveCategory
```

**Path only:** `/ccadmin/cms/api/ModuleApi/SaveCategory`

---

## 2. Headers

| Key                  | Value              |
|----------------------|--------------------|
| `Content-Type`       | `application/json` |
| `ms_cms_clientapp`   | `ProgrammingApp`   |
| `Authorization`      | `Bearer <YOUR_CMS_LOGIN_TOKEN>` |

Use the same **CMS Login Token** from your pipeline config (the one used after "Generating Login Token" step).

---

## 3. Body (raw JSON)

Example for **"Our Resort"** – same structure the app sends:

```json
{
  "ModuleCategory": {
    "CategoryId": 0,
    "ParentCategory": 0,
    "CategoryName": "Our Resort",
    "CategoryAlias": "our-resort",
    "ResourceTypeID": 1,
    "ResourceTypeIdForMultipleImages": 0,
    "categorystatus": 1,
    "MilestoneModuleCategoryID": 0,
    "ModuleIdentifier": "MODULE_OUR_RESORT",
    "ShowSnippets": 0,
    "TopNavigationFormatId": 0,
    "ModuleOrder": 1,
    "SchemaBusinessTypeDetailID": 0,
    "IsEnableRedirection": false,
    "RedirectionURL": "",
    "SiteId": 17158
  }
}
```

**Important:** Use the **correct Site ID for this project** (e.g. **17158**). A wrong SiteId (e.g. 17259 from another project) can cause **404** or rejection because the API checks that the site exists and that your token is authorized for that site.

**Notes:**
- **CategoryId:** `0` = create new; use existing ID to update.
- **ParentCategory:** `0` = root; or parent category ID for a child.
- **CategoryName:** Display name (e.g. "Our Resort").
- **CategoryAlias:** Slug from name (lowercase, spaces → `-`, non-alphanumeric removed).
- **ModuleIdentifier:** `MODULE_` + alias in UPPER_SNAKE (e.g. `MODULE_OUR_RESORT`).
- **SiteId:** Your site ID from config (e.g. `17158` for this project). **Must match the site** the token is for; wrong site ID can cause 404.

For another page, e.g. "Dining":
- CategoryName: `"Dining"`
- CategoryAlias: `"dining"`
- ModuleIdentifier: `"MODULE_DINING"`
- SiteId: same as above.

---

## 4. Postman setup

1. **New request** → Method **POST**.
2. **URL:** `https://<your-cms-host>/ccadmin/cms/api/ModuleApi/SaveCategory`.
3. **Headers** tab: add the three headers above; set `Authorization` to `Bearer <token>`.
4. **Body** tab: choose **raw**, type **JSON**, paste the JSON from section 3.
5. Ensure `SiteId` in the body matches your project (e.g. **17158**). Then send.

---

## 5. Expected responses

- **200 OK:** Category created or updated; response body usually contains the saved category (e.g. with `CategoryId`).
- **404 Not Found:** Endpoint or resource not found – confirm base URL and that this API is enabled for your environment.
- **401:** Invalid or expired token – regenerate CMS Login Token.
- **400:** Bad request – check JSON and required fields for your CMS version.

If you get 404, try with the **ccadmin** path exactly as above; some setups use a different base path (e.g. `/api/` instead of `/ccadmin/cms/api/`).
