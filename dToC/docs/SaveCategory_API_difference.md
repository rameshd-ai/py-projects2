# Why SaveCategory May Fail When Other APIs Succeed

## Difference: URL path prefix

| API | Path | In this project |
|-----|------|------------------|
| **GetPageCategoryList** (category list – works) | `{base_url}/api/PageApi/GetPageCategoryList` | No `ccadmin/cms` |
| **SaveCategory** (create category – fails) | `{base_url}/ccadmin/cms/api/ModuleApi/SaveCategory` | Uses `ccadmin/cms` |

So in the same flow:

- The **category list** call uses the shorter path: **`/api/...`**.
- The **SaveCategory** call is the only one using **`/ccadmin/cms/api/ModuleApi/...`**.

If your environment exposes **ModuleApi** only under `/api/` (and not under `/ccadmin/cms/api/`), the current SaveCategory URL would return **404**, while GetPageCategoryList would still work.

## What to try

1. **Use the alternate path in Postman**  
   Try the same request body and headers but with:
   - **URL:** `https://<your-cms-host>/api/ModuleApi/SaveCategory`  
   (i.e. **without** `ccadmin/cms` in the path.)

2. **If that works**, the app should use the shorter path for SaveCategory. You can enable the fallback in code (see below) or change the default URL in `apis.py` to use `/api/ModuleApi/SaveCategory`.

3. **Confirm with backend/Swagger**  
   Check which base path is correct for **ModuleApi** in your environment: `/api/` or `/ccadmin/cms/api/`.

## Other possible causes

- **SiteId** in the body must match your project (e.g. **17158**); wrong site can cause 404 or rejection.
- **Headers** are the same as for GetPageCategoryList (`Content-Type`, `ms_cms_clientapp`, `Authorization`), so header difference is unlikely if the category list works.
