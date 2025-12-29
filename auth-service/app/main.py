from fastapi.openapi.docs import get_swagger_ui_html
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import api_router
from app.core.error_handlers import (
    service_exception_handler,
    validation_exception_handler,
    sqlalchemy_exception_handler,
    general_exception_handler
)
from app.core.exceptions import BaseServiceException


app = FastAPI(
    docs_url=None,
    title="Auth Service",
    description="Authentication and authorization service",
    version="1.0.0"
)

app.add_exception_handler(BaseServiceException, service_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "auth-service"}

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        swagger_ui_parameters={"syntaxHighlight.theme": "obsidian"},
        swagger_css_url="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.10.5/swagger-ui.min.css",
        swagger_js_url="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.10.5/swagger-ui-bundle.js",
    ) 

@app.get("/custom-docs", include_in_schema=False)
async def dark_swagger_ui_html():
    """
    Custom dark theme Swagger UI with inline CSS
    """
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
            const ui = SwaggerUIBundle({{
                url: '{app.openapi_url}',
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


@app.get("/dark-docs", include_in_schema=False)
async def better_dark_swagger():
    """
    Better dark theme implementation with custom CSS
    """
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{app.title} - API Documentation</title>
        <link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.10.5/swagger-ui.min.css">
        <link rel="icon" type="image/png" href="https://fastapi.tiangolo.com/img/favicon.png">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background: #1e1e1e;
            }}
            
            .swagger-ui {{
                background: #1e1e1e;
            }}
            
            .swagger-ui .topbar {{
                background-color: #2d2d2d;
                padding: 10px 0;
            }}
            
            .swagger-ui .info .title {{
                color: #ffffff !important;
            }}
            
            .swagger-ui .info p,
            .swagger-ui .info a,
            .swagger-ui .scheme-container {{
                color: #b4b4b4;
            }}
            
            .swagger-ui .opblock-tag {{
                color: #ffffff;
                border-bottom: 1px solid #3a3a3a;
            }}
            
            .swagger-ui .opblock {{
                background: #2d2d2d;
                border: 1px solid #3a3a3a;
            }}
            
            .swagger-ui .opblock .opblock-summary {{
                border: none;
            }}
            
            .swagger-ui .opblock.opblock-get {{
                background: rgba(97, 175, 254, 0.1);
                border-color: #61affe;
            }}
            
            .swagger-ui .opblock.opblock-post {{
                background: rgba(73, 204, 144, 0.1);
                border-color: #49cc90;
            }}
            
            .swagger-ui .opblock.opblock-put {{
                background: rgba(252, 161, 48, 0.1);
                border-color: #fca130;
            }}
            
            .swagger-ui .opblock.opblock-delete {{
                background: rgba(249, 62, 62, 0.1);
                border-color: #f93e3e;
            }}
            
            .swagger-ui .opblock-summary-method {{
                background: #1e1e1e;
            }}
            
            .swagger-ui .opblock-description-wrapper p,
            .swagger-ui .opblock-external-docs-wrapper p,
            .swagger-ui .opblock-title_normal p {{
                color: #b4b4b4;
            }}
            
            .swagger-ui .parameters-col_description p {{
                color: #b4b4b4;
            }}
            
            .swagger-ui table thead tr th,
            .swagger-ui table tbody tr td {{
                color: #b4b4b4;
                border-color: #3a3a3a;
            }}
            
            .swagger-ui .model-box,
            .swagger-ui .model {{
                background: #2d2d2d;
            }}
            
            .swagger-ui .prop-type {{
                color: #61affe;
            }}
            
            .swagger-ui .response-col_status {{
                color: #b4b4b4;
            }}
            
            .swagger-ui .response-col_description {{
                color: #b4b4b4;
            }}
            
            .swagger-ui .btn {{
                background: #3a3a3a;
                color: #ffffff;
                border-color: #3a3a3a;
            }}
            
            .swagger-ui .btn:hover {{
                background: #4a4a4a;
            }}
            
            .swagger-ui textarea {{
                background: #1e1e1e;
                color: #ffffff;
                border-color: #3a3a3a;
            }}
            
            .swagger-ui input[type=text],
            .swagger-ui input[type=email],
            .swagger-ui input[type=password] {{
                background: #1e1e1e;
                color: #ffffff;
                border-color: #3a3a3a;
            }}
            
            .swagger-ui select {{
                background: #1e1e1e;
                color: #ffffff;
                border-color: #3a3a3a;
            }}
            
            .swagger-ui .highlighted-code {{
                background: #1e1e1e;
            }}
            
            .swagger-ui .microlight {{
                background: #1e1e1e !important;
                color: #a9b7c6 !important;
            }}
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.10.5/swagger-ui-bundle.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.10.5/swagger-ui-standalone-preset.js"></script>
        <script>
            const ui = SwaggerUIBundle({{
                url: '{app.openapi_url}',
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)