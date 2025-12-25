import os
from app.main import app
from shared.config import get_settings
from shared.logging_config import setup_logging



settings = get_settings()
setup_logging(service_name=settings.app.service_name, log_level=settings.app.log_level)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)