# Dev Container Configuration

## Important: All Services Run Automatically

When you open this project in a Dev Container, **all services** (auth, product, order, notification) are started automatically via docker-compose, regardless of which container you choose as your workspace.

## Switching Service Containers

The `service` field in `.devcontainer/devcontainer.json` determines which container VS Code uses as your workspace (for terminal, file access, etc.).

### To Switch Containers:

1. Edit `.devcontainer/devcontainer.json`
2. Change the `"service"` field to one of:
   - `"auth-service"` - Auth Service container
   - `"product-service"` - Product Service container  
   - `"order-service"` - Order Service container
   - `"notification-service"` - Notification Service container
3. Press `Ctrl+Shift+P` → "Dev Containers: Rebuild Container"

## Debugging Any Service

You can debug **any service** from **any container** because all containers are on the same Docker network. Just use the launch configurations in `.vscode/launch.json`:

- **Python: Debug Auth Service** (port 5678)
- **Python: Debug Product Service** (port 5679)
- **Python: Debug Order Service** (port 5680)
- **Python: Debug Notification Service** (port 5681)

## Quick Start

1. Press `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
2. Wait for all services to start
3. Set breakpoints in any service
4. Press `F5` and select the debug configuration for the service you want to debug

