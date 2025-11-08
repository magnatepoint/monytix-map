# Fix: Supabase Web OAuth Redirect Issue

## Problem
The web application is trying to use the mobile custom URL scheme `io.supabase.monytix://login-callback` instead of an HTTP/HTTPS URL. This causes the error:
```
Failed to launch 'io.supabase.monytix://login-callback/?code=...' because the scheme does not have a registered handler.
```

## Root Cause
The Supabase Dashboard "Site URL" is set to the custom scheme `io.supabase.monytix://login-callback`, which overrides the `redirectTo` parameter in the code.

## Solution

### Step 1: Update Supabase Dashboard Configuration

1. **Go to Supabase Dashboard:**
   - URL: https://supabase.com/dashboard/project/vwagtikpxbhjrffolrqn/auth/url-configuration
   - Or: Dashboard → Your Project → Authentication → URL Configuration

2. **Update "Site URL":**
   - **Current (WRONG):** `io.supabase.monytix://login-callback`
   - **Change to (CORRECT):** Your web app URL
     - Production: `https://monytix-map.pages.dev` (or your Cloudflare Pages URL)
     - Local dev: `http://localhost:55860`

3. **Update "Redirect URLs" list:**
   Add all the URLs where users can be redirected after authentication:
   
   **For Production:**
   - `https://monytix-map.pages.dev/callback`
   - `https://monytix-map.pages.dev/*` (wildcard for all paths)
   
   **For Local Development:**
   - `http://localhost:55860/callback`
   - `http://localhost:55860/*`
   
   **For Mobile (keep these):**
   - `io.supabase.monytix://login-callback`
   - `io.supabase.monytix://*`

### Step 2: Verify Configuration

After updating:
1. The **Site URL** should be an HTTP/HTTPS URL (not a custom scheme)
2. The **Redirect URLs** should include:
   - Your web app callback URLs (HTTP/HTTPS)
   - Your mobile custom scheme URLs

### Step 3: Test

1. **Clear browser cache** (important!)
2. **Restart your Flutter web app**
3. **Try signing in with Google**
4. **Check the browser console** - you should see:
   - `🌐 Web platform detected - using redirect URL: http://localhost:55860/callback`
   - No errors about custom URL schemes

## Important Notes

- **Site URL** is the default redirect URL used when `redirectTo` is not specified
- **Redirect URLs** is a whitelist of allowed redirect URLs
- The custom scheme `io.supabase.monytix://login-callback` should **only** be in the Redirect URLs list, **not** as the Site URL
- The Site URL should be your web app's base URL (without `/callback`)

## Example Configuration

**Site URL:**
```
https://monytix-map.pages.dev
```

**Redirect URLs:**
```
https://monytix-map.pages.dev/callback
https://monytix-map.pages.dev/*
http://localhost:55860/callback
http://localhost:55860/*
io.supabase.monytix://login-callback
io.supabase.monytix://*
```

