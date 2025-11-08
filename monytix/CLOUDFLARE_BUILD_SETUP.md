# Cloudflare Pages Build Configuration

## Build Settings

Since Cloudflare Pages doesn't have native Flutter support, you need to configure it manually:

### Option 1: Use Custom Build Command (Recommended)

In your Cloudflare Pages project settings:

1. Go to **Settings** → **Builds & deployments**
2. Set the following:

**Build command:**
```bash
bash monytix/build-cloudflare.sh
```

**Build output directory:**
```
monytix/build/web
```

**Root directory:**
```
/ (leave empty)
```

**Environment variables:**
- `API_BASE_URL` = `https://backend.mallaapp.org`
- `SUPABASE_URL` = `https://vwagtikpxbhjrffolrqn.supabase.co`
- `SUPABASE_PUBLISHABLE_KEY` = (your publishable key from Supabase)

### Option 2: Use GitHub Actions (Already Configured)

The GitHub Actions workflow is already set up at `.github/workflows/deploy-cloudflare.yml`.

**You need to add these secrets to GitHub:**
1. Go to: https://github.com/magnatepoint/monytix-map/settings/secrets/actions
2. Add:
   - `CLOUDFLARE_API_TOKEN` - Get from: https://dash.cloudflare.com/profile/api-tokens
   - `CLOUDFLARE_ACCOUNT_ID` - Get from Cloudflare dashboard (right sidebar)
   - `API_BASE_URL` = `https://backend.mallaapp.org` (optional, has default)
   - `SUPABASE_URL` = `https://vwagtikpxbhjrffolrqn.supabase.co` (optional, has default)
   - `SUPABASE_PUBLISHABLE_KEY` = (your publishable key) (optional)

Then push to trigger deployment:
```bash
git push
```

### Option 3: Simplified Build Command (If Flutter is pre-installed)

If Cloudflare Pages has Flutter available, use:

**Build command:**
```bash
cd monytix && flutter pub get && flutter build web --release && echo "/*    /index.html   200" > build/web/_redirects
```

**Build output directory:**
```
monytix/build/web
```

## Important Notes

- Cloudflare Pages doesn't have native Flutter support, so you need to install Flutter in the build script
- The build script (`build-cloudflare.sh`) downloads and installs Flutter SDK
- Make sure to add environment variables in Cloudflare Pages settings
- The `_redirects` file is automatically created for SPA routing

## Troubleshooting

If the build fails:
1. Check the build logs for Flutter installation errors
2. Verify the build command is correct
3. Make sure the build output directory matches `monytix/build/web`
4. Ensure environment variables are set correctly

