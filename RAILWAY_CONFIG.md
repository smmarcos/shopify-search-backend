# Railway Configuration Guide

## Required Environment Variables

### Backend Service (shopify-search-backend)

1. **OPENAI_API_KEY** (required)
   - Your OpenAI API key for embeddings and AI search
   - Format: `sk-proj-...`
   - Get it from: https://platform.openai.com/api-keys

2. **DATABASE_URL** (required)
   - Connection to PostgreSQL with pgvector
   - In Railway, use: `${{pgvector.DATABASE_URL}}`
   - This references the pgvector service automatically

3. **PORT** (auto-provided by Railway)
   - Railway provides this automatically
   - Default: 8000 (fallback in Dockerfile)

### Frontend Service (web)

1. **BACKEND_URL** (required)
   - URL to the backend service
   - For Railway internal networking: `https://shopify-search-backend.railway.internal`
   - For public access: Use the generated Railway URL

2. **SESSION_SECRET** (recommended)
   - Secret for session encryption
   - Generate with: `openssl rand -base64 32`

3. **SHOPIFY_API_KEY** (required)
   - From your Shopify Partner Dashboard
   
4. **SHOPIFY_API_SECRET** (required)
   - From your Shopify Partner Dashboard

## Railway Services Setup

### 1. PostgreSQL with pgvector (pgvector)
```
✓ Already created
✓ Volume: pgvector-volume attached
✓ Status: Online
```

### 2. Backend Service (shopify-search-backend)
```
Repository: https://github.com/smmarcos/shopify-search-backend
Branch: main
Build: Dockerfile detected automatically
Root Directory: / (default)

Environment Variables:
- OPENAI_API_KEY=<your-openai-key>
- DATABASE_URL=${{pgvector.DATABASE_URL}}

Port: 8000 (exposed in Dockerfile)
Health Check: /health endpoint
```

### 3. Frontend Service (web)
```
Repository: https://github.com/smmarcos/shopify-search-ai
Branch: main
Root Directory: / (default)

Environment Variables:
- BACKEND_URL=https://shopify-search-backend.railway.internal
- SESSION_SECRET=<generate-random-secret>
- SHOPIFY_API_KEY=<from-partner-dashboard>
- SHOPIFY_API_SECRET=<from-partner-dashboard>

Public Domain: ✓ Generated automatically
Health Check: / endpoint
```

## Networking

Railway provides automatic service discovery:
- Internal DNS: `<service-name>.railway.internal`
- Frontend can reach backend at: `shopify-search-backend.railway.internal`
- No need to expose backend publicly

## Deployment Flow

1. **Push to GitHub** → Automatic deployment
2. **Build logs** → Check for errors
3. **Deploy logs** → Verify startup
4. **Health check** → Service becomes available

## Testing

1. Check backend health:
   ```bash
   curl https://shopify-search-backend-production.up.railway.app/health
   ```

2. Check frontend:
   ```bash
   curl https://web-production-b3dac1.up.railway.app/
   ```

3. Test search from frontend:
   - Open Shopify admin
   - Navigate to app
   - Try search functionality

## Troubleshooting

### Backend fails to start
- Check `OPENAI_API_KEY` is set correctly
- Verify `DATABASE_URL` references pgvector service
- Review deploy logs for Python errors

### Frontend can't connect to backend
- Verify `BACKEND_URL` is set to internal Railway URL
- Check backend service is running (status: Online)
- Review HTTP logs for connection errors

### Database connection errors
- Ensure pgvector service is online
- Check `DATABASE_URL` format in backend
- Verify pgvector extension is installed

## Current Status (as of deployment)

✅ Frontend (web): Online
⏳ Backend (shopify-search-backend): Deploying
✅ Database (pgvector): Online

**Next Steps:**
1. Wait for backend deployment to complete
2. Configure OPENAI_API_KEY in backend service
3. Test search functionality
4. Monitor logs for any errors
