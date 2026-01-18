#!/bin/bash

function login() {
    if [ $# -lt 2 ]; then
        echo "Error: Missing required arguments"
        echo "Usage: login <email> <password>"
        echo ""
        echo "Example: login \"user@example.com\" \"Password123\""
        return 1
    fi
    
    response=$(curl -X POST http://localhost:8080/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$1\", \"password\": \"$2\"}")

    ACCESS_TOKEN=$(jq -r '.tokens.access_token' <<< "$response")
    REFRESH_TOKEN=$(jq -r '.tokens.refresh_token' <<< "$response")

    echo "access_token and refresh_token are saved in the environment variables"
    jq <<< "{\"access_token\": \"$ACCESS_TOKEN\", \"refresh_token\": \"$REFRESH_TOKEN\"}"
    return 0
}

function refresh_token() {
    if [ -z "$REFRESH_TOKEN" ]; then
        echo "Error: REFRESH_TOKEN environment variable is not set"
        echo "Please login first using: login <email> <password>"
        return 1
    fi
    
    response=$(curl -X POST http://localhost:8080/api/v1/auth/refresh \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")

    ACCESS_TOKEN=$(jq -r '.access_token' <<< "$response")
    REFRESH_TOKEN=$(jq -r '.refresh_token' <<< "$response")

    echo "access_token and refresh_token are saved in the environment variables"
    jq <<< "{\"access_token\": \"$ACCESS_TOKEN\", \"refresh_token\": \"$REFRESH_TOKEN\"}"
    return 0
}

function create_product() {
    if [ $# -lt 4 ]; then
        echo "Error: Missing required arguments"
        echo "Usage: create_product <name> <price> <stock> <status>"
        echo ""
        echo "Arguments:"
        echo "  name   - Product name (string)"
        echo "  price  - Product price (number, must be > 0)"
        echo "  stock  - Stock quantity (integer, >= 0)"
        echo "  status - Product status (active, inactive, out_of_stock, discontinued, draft)"
        echo ""
        echo "Example: create_product \"name=Laptop\" \"price=999.99\" \"stock=10\" \"status=active\""
        return 1
    fi
    local name price stock status
    
    for arg in "$@"; do
        case $arg in
            name=*)
                name="${arg#*=}"
                ;;
            price=*)
                price="${arg#*=}"
                ;;
            stock=*)
                stock="${arg#*=}"
                ;;
            status=*)
                status="${arg#*=}"
                ;;
            *)
                echo "Unknown argument: $arg"
                return 1
                ;;  
        esac
    done
    
    curl -X POST http://localhost:8080/api/v1/products \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$name\", \"price\": \"$price\", \"stock\": \"$stock\", \"status\": \"$status\"}" \
    | jq
    return 0
}
