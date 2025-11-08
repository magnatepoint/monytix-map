from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import uvicorn
import os
from config import settings
from app.routers import transactions as transactions_router
from app.routers import ml as ml_router
from app.routers import auth as auth_router
from app.core.websocket_manager import websocket_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Monytix API...")
    
    # Initialize database tables
    try:
        from app.database.postgresql import init_db
        init_db()
        print("✅ Database tables initialized")
    except Exception as e:
        print(f"⚠️  Database initialization warning: {e}")
        print("   Tables may be created on-demand...")
    
    # Initialize MongoDB connection
    try:
        from app.database.mongodb import connect_to_mongo, close_mongo_connection
        await connect_to_mongo()
    except Exception as e:
        print(f"⚠️  MongoDB connection failed: {e}")
        print("   Continuing without MongoDB...")
    yield
    # Shutdown
    try:
        from app.database.mongodb import close_mongo_connection
        await close_mongo_connection()
    except:
        pass
    print("👋 Shutting down Monytix API...")


app = FastAPI(
    title="Monytix API",
    description="Fintech backend for transaction processing and ML insights",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
# Allow origins from environment or default to localhost for development
# Production: Set CORS_ORIGINS env var with comma-separated list like:
# CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:55860,https://mallaapp.org,https://app.mallaapp.org
default_origins = "http://localhost:5173,http://localhost:3000,http://localhost:55860,https://mallaapp.org,https://app.mallaapp.org,https://frontend.mallaapp.org,https://backend.mallaapp.org"
allowed_origins = os.getenv("CORS_ORIGINS", default_origins).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Exception handler to ensure CORS headers on unhandled errors
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Ensure CORS headers on HTTP exceptions"""
    # Get the origin from the request
    origin = request.headers.get("origin")
    # Check if origin is in allowed origins
    cors_origin = origin if origin and origin in allowed_origins else (allowed_origins[0] if allowed_origins else "*")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Ensure CORS headers are included in all error responses"""
    import traceback
    print(f"❌ Unhandled exception: {exc}")
    print(traceback.format_exc())
    
    # Get the origin from the request
    origin = request.headers.get("origin")
    # Check if origin is in allowed origins
    cors_origin = origin if origin and origin in allowed_origins else (allowed_origins[0] if allowed_origins else "*")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

# Import additional routers
from app.routers import uploads as uploads_router
from app.routers import etl as etl_router
from app.routers import enrichment as enrichment_router
from app.routers import spendsense as spendsense_router
from app.routers import goals as goals_router
from app.routers import budgetpilot as budgetpilot_router
from app.routers import goalcompass as goalcompass_router
from app.routers import moneymoments as moneymoments_router
from app.routers import categories as categories_router

# Include routers
app.include_router(auth_router.router, prefix="/auth", tags=["Authentication"])
app.include_router(transactions_router.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(ml_router.router, prefix="/api/ml", tags=["ML"])
app.include_router(uploads_router.router, prefix="/api/upload", tags=["Uploads"])
app.include_router(etl_router.router, prefix="/api/etl", tags=["ETL Pipeline"])
app.include_router(enrichment_router.router, prefix="/api/enrichment", tags=["Enrichment"])
app.include_router(spendsense_router.router, prefix="/api/spendsense", tags=["SpendSense"])
app.include_router(goals_router.router, prefix="/api/goals", tags=["Goals"])
app.include_router(budgetpilot_router.router, prefix="/api/budgetpilot", tags=["BudgetPilot"])
app.include_router(goalcompass_router.router, prefix="/api/goalcompass", tags=["GoalCompass"])
app.include_router(moneymoments_router.router, prefix="/api/moneymoments", tags=["MoneyMoments"])
app.include_router(categories_router.router, prefix="/api", tags=["Categories"])


@app.get("/")
async def root():
    return {"message": "Monytix API is running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/debug/db")
async def debug_database():
    """Debug endpoint to check database connectivity and schema"""
    from app.database.postgresql import SessionLocal
    from sqlalchemy import text
    
    session = SessionLocal()
    try:
        results = {
            "database_connected": True,
            "schemas": {},
            "tables": {}
        }
        
        # Check if spendsense schema exists
        schema_check = session.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.schemata 
                WHERE schema_name = 'spendsense'
            )
        """)).scalar()
        results["schemas"]["spendsense"] = schema_check
        
        if schema_check:
            # List tables in spendsense schema
            tables = session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'spendsense'
                ORDER BY table_name
            """)).fetchall()
            results["tables"]["spendsense"] = [t[0] for t in tables]
            
            # Check key tables
            key_tables = ["txn_staging", "txn_fact", "txn_enriched", "dim_category"]
            for table in key_tables:
                exists = session.execute(text(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = 'spendsense' 
                        AND table_name = '{table}'
                    )
                """)).scalar()
                results["tables"][f"spendsense.{table}"] = exists
        
        # Check staging tables
        staging_tables = session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name IN ('gmail_connections', 'upload_batch', 'transaction_staging')
            ORDER BY table_name
        """)).fetchall()
        results["tables"]["staging"] = [t[0] for t in staging_tables]
        
        return results
    except Exception as e:
        import traceback
        return {
            "database_connected": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
    finally:
        session.close()


# WebSocket endpoint for real-time updates
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now - can be extended for specific commands
            await websocket_manager.send_personal_message(f"Message: {data}", user_id)
    except WebSocketDisconnect:
        websocket_manager.disconnect(user_id)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.environment == "development" else False
    )

