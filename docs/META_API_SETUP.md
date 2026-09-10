# Meta API setup for Creator Discovery

Creator Discovery uses only the official Meta Graph API. Credentials stay in the backend `.env`; they are never sent to React or written to logs. This implementation defaults to Graph API `v26.0`, is covered by mocked contract tests, and keeps the version configurable because Meta versions and permissions change over time.

## Values to obtain

Copy `.env.example` to `.env`, then fill the following block.

| Environment variable | Where the value comes from | Required | Purpose |
| --- | --- | --- | --- |
| `META_APP_ID` | Meta App Dashboard → App settings → Basic → App ID | Yes | Verifies that the token belongs to the configured app. |
| `META_APP_SECRET` | Meta App Dashboard → App settings → Basic → App secret | Yes | Server-side token debugging and `appsecret_proof`; never expose it to the browser. |
| `META_ACCESS_TOKEN` | A Meta user or Page access token issued to the app with the approved permissions below | Yes | Authenticates Graph API reads. Prefer the appropriate long-lived production token. |
| `META_GRAPH_API_VERSION` | A currently supported Graph API version selected for your app | Yes; default `v26.0` | Pins requests so an unannounced default-version change cannot alter behavior. |
| `META_FACEBOOK_PAGE_ID` | Graph API Explorer or `GET /me/accounts?fields=id,name` | Required for Facebook | Identifies the authorized Page used and validated by the Facebook connector. |
| `META_INSTAGRAM_ACCOUNT_ID` | `instagram_business_account.id` from the linked Page query below | Required for Instagram | Identifies the authorized Instagram Professional account used for own-account reads and Business Discovery. |

No real values belong in `.env.example`. `.env` is already ignored by Git.

## Meta app configuration

1. Create or select a Meta developer app that supports the Instagram API with Facebook Login and Facebook Pages APIs.
2. Add Facebook Login for Business / the applicable business-login product and the Instagram API product required by the current Meta dashboard flow.
3. Add the Facebook Page and its linked Instagram Professional account to the same Meta Business portfolio. The Instagram account must be a Business or Creator account, not a consumer/personal account.
4. Give the authenticating Facebook user an appropriate role on the Page and access to the linked Instagram account.
5. Configure a valid OAuth redirect URI if you generate tokens through your own production login flow. For local operator setup, Meta's Graph API Explorer can be used for a test token; do not treat its short-lived token as production-ready.
6. Request App Review and business verification when Meta requires them for data outside app-role/test accounts.

The connector checks these permissions in its supported Facebook Login flow:

- Instagram: `instagram_basic`, `pages_read_engagement`, `pages_show_list`
- Facebook Pages: `pages_read_engagement`, `pages_show_list`

Meta can require additional review/features for public Page content, Business Discovery, insights, or accounts outside the app's roles. Grant only the permissions the app actually needs. This connector does not publish, message, delete, or modify Meta content.

## Find the Page and Instagram IDs

With a token that has Page-list access, call the versioned Graph API:

```text
GET /me/accounts?fields=id,name,username,instagram_business_account{id,username,name}
```

Use the selected Page `id` as `META_FACEBOOK_PAGE_ID`. Use its `instagram_business_account.id` as `META_INSTAGRAM_ACCOUNT_ID`. If `instagram_business_account` is absent, link the Instagram Professional account to the Page in Meta and try again. Do not paste the Page access token or response into source code.

## Token validation and startup

After editing `.env`:

1. Restart the backend so settings reload.
2. Open Creator Discovery → Connections.
3. Select **VALIDATE CONNECTION**.
4. Confirm the token status and each platform status. `READY` is returned only after `/debug_token` succeeds, the token is associated with `META_APP_ID`, required scopes are present, and the configured account object is readable.
5. Run discovery with a direct Instagram or Facebook profile URL, or use **Refresh public data** on an existing creator.

The UI receives only configured YES/NO flags, a last-four-character token hint, validation time, scopes, and account/capability status. It never receives the App Secret or full token.

## Supported collection behavior

- Instagram direct URLs use the authorized Instagram Professional account. Its own profile is read directly; another Professional account is attempted through official Business Discovery. Arbitrary name search is not offered, so name-only discovery returns `DIRECT_URL_REQUIRED`.
- Facebook direct URLs attempt an official Page lookup under the configured app/token permissions. Personal profiles are not scraped or treated as Pages. Name-only discovery returns `DIRECT_URL_REQUIRED`.
- Recent content is capped by Creator Discovery's selected Content Sample Size (maximum 30). Only fields returned by Meta are stored. Missing counts or media fields remain null.
- Each profile field and content sample records `source=meta_api`, platform, Graph object ID, retrieved time, returned field names, and a source/permalink when available.
- Refresh updates the existing platform account and content samples in place; it does not create a duplicate creator.

## Token lifetime

The validation endpoint reads Meta's token debug response and reports an expiry time when Meta supplies one. Replace an expired or invalidated token in `.env`, restart the backend, and validate again. The application never invents or automatically rotates credentials.

## Common statuses

| Status | Meaning / action |
| --- | --- |
| `NOT_CONFIGURED` | One or more core credentials are blank. Fill `.env` and restart. |
| `TOKEN_INVALID` | Meta rejected the token or it belongs to a different App ID. Generate a token for this app. |
| `TOKEN_EXPIRED` | The debug response or Graph error says the token expired. Replace it. |
| `PERMISSION_MISSING` | Add the listed permission to the login grant and complete App Review if required. |
| `ACCOUNT_NOT_LINKED` | The Page or Instagram account ID is missing or not linked for this token. |
| `ACCOUNT_NOT_ACCESSIBLE` | The requested URL is outside the app/token's official access or is not a supported Page/Professional account. |
| `RATE_LIMITED` | Meta throttled the request. The client performs only bounded backoff; wait before retrying. |
| `API_UNAVAILABLE` | A temporary Graph/network failure occurred. Retry later. |

Official references:

- [Meta Graph API](https://developers.facebook.com/docs/graph-api/)
- [Instagram API with Facebook Login](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/)
- [Instagram Business Discovery](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery/)
- [Access-token debugging](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/debugging-and-error-handling/)
- [Graph API versioning](https://developers.facebook.com/docs/graph-api/guides/versioning/)

