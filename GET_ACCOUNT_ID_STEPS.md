# Get Account ID Using API

## Step 1: Get Your API Token

1. Go to: https://dash.cloudflare.com/profile/api-tokens
2. Click **"Create Token"**
3. Use **"Edit Cloudflare Workers"** template
4. Click **"Continue to summary"** → **"Create Token"**
5. **Copy the token** (you won't see it again!)

## Step 2: Use the Token to Get Account ID

Once you have your token, run this command (replace `YOUR_ACTUAL_TOKEN` with your real token):

```bash
curl -X GET "https://api.cloudflare.com/client/v4/accounts" \
  -H "Authorization: Bearer YOUR_ACTUAL_TOKEN" \
  -H "Content-Type: application/json"
```

This will return JSON with your accounts, including the Account ID.

## Step 3: Extract Account ID

The response will look like:
```json
{
  "result": [
    {
      "id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
      "name": "Santoshmalla221989@gmail.com's Account",
      ...
    }
  ]
}
```

The `id` field is your Account ID!

## Alternative: Just Add API Token to GitHub

If you want to skip finding the Account ID for now:

1. **Add `CLOUDFLARE_API_TOKEN` to GitHub secrets**
2. **Don't add `CLOUDFLARE_ACCOUNT_ID` yet**
3. **Push and see what happens**

The workflow might work without it, or the error message might tell us where to find it!

