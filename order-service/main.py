from fastapi import FastAPI, Request
import os
from contextlib import asynccontextmanager
from starlette.responses import HTMLResponse

from app.api.v1 import orders
from app.core.database import init_db
from app.core.product_client import close_product_client
from app.core.event_consumer import start_event_consumer, stop_event_consumer
from shared.logging_config import setup_logging, get_logger
from shared.config import get_settings

settings = get_settings()
setup_logging(service_name=os.getenv("SERVICE_NAME", "order-service"), log_level=settings.app.log_level)
logger = get_logger(__name__, os.getenv("SERVICE_NAME", "order-service"))
logger.debug(f'log level: {settings.app.log_level}')


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting order-service...")
    try:
        init_db()
        logger.info("Database initialized")
        
        try:
            await start_event_consumer()
            logger.info("Event consumer started")
        except Exception as e:
            logger.error(f"Error starting event consumer: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    
    yield
    
    logger.info("Shutting down order-service...")
    try:
        await stop_event_consumer()
        logger.info("Event consumer stopped")
    except Exception as e:
        logger.error(f"Error stopping event consumer: {e}", exc_info=True)
    
    await close_product_client()
    logger.info("Order service shut down complete")


app = FastAPI(
    title="Order Service",
    description="Order management service for TheOne ecommerce platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
)

app.include_router(orders.router)


@app.get("/")
def read_root():
    return {"message": "order-service", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "order-service"}


@app.get("/custom-docs", include_in_schema=False)
async def dark_swagger_ui_html(request: Request):
    """
    Custom dark theme Swagger UI with inline CSS
    """
    # Determine the correct OpenAPI URL dynamically using JavaScript
    # This handles both direct access and access through nginx gateway
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{app.title} - Swagger UI</title>
        <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.10.5/swagger-ui.min.css">
        <link rel="icon" type="image/png" href="https://fastapi.tiangolo.com/img/favicon.png">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background: #1a1a1a;
            }}
            
            .swagger-ui {{
                filter: invert(88%) hue-rotate(180deg);
            }}
            
            .swagger-ui .topbar {{
                background-color: #1a1a1a;
                border-bottom: 1px solid #3a3a3a;
            }}
            
            .swagger-ui .info .title {{
                color: #ffffff;
            }}
            
            /* Fix images and syntax highlighting */
            .swagger-ui img {{
                filter: invert(100%) hue-rotate(180deg);
            }}
            
            .swagger-ui .microlight {{
                filter: invert(100%) hue-rotate(180deg);
            }}
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.10.5/swagger-ui-bundle.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.10.5/swagger-ui-standalone-preset.js"></script>
        <script>
            // Dynamically determine the OpenAPI URL based on the current path
            const currentPath = window.location.pathname;
            let openapiUrl = '/openapi.json';
            
            // If accessed through nginx gateway at /orders/custom-docs, use /orders/openapi.json
            if (currentPath.includes('/orders/custom-docs')) {{
                openapiUrl = '/orders/openapi.json';
            }}
            
            const ui = SwaggerUIBundle({{
                url: openapiUrl,
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true,
                syntaxHighlight: {{
                    theme: "monokai"
                }}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)




# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8002)
