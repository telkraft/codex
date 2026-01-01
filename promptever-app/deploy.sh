#!/bin/bash
# /opt/promptever-app/deploy.sh
# Promptever App - React Frontend Deployment
# Usage: ./deploy.sh [setup|start|stop|restart|logs|status|build]

set -e

PROJECT_NAME="promptever-app"
BASE_DIR="/opt/${PROJECT_NAME}"
DOMAIN="app.promptever.com"
EMAIL="can@promptever.com"
SERVER_IP="148.230.111.158"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║     Promptever App - Enterprise Experience Analytics       ║"
    echo "║                    React Frontend v1.0                     ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_requirements() {
    log_info "Checking requirements..."
    
    # Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check xapia_net network
    if ! docker network ls | grep -q "xapia_net"; then
        log_warn "xapia_net network not found. Creating..."
        docker network create xapia_net
    fi
    
    # Check if rag-api is running (optional but recommended)
    if docker ps | grep -q "rag-api"; then
        log_info "✓ rag-api backend is running"
    else
        log_warn "rag-api not running. App will work but API calls may fail."
    fi
    
    log_info "✓ Requirements OK"
}

setup() {
    print_banner
    log_step "Starting Promptever App setup..."
    
    check_requirements
    
    # Create directories
    log_info "Creating directory structure..."
    mkdir -p ${BASE_DIR}/{nginx/ssl,src}
    
    # Check DNS
    log_info "Checking DNS for ${DOMAIN}..."
    if host ${DOMAIN} 2>/dev/null | grep -q "${SERVER_IP}"; then
        log_info "✓ DNS is configured"
    else
        log_warn "DNS not configured or not propagated yet"
        log_info "Add A record: ${DOMAIN} → ${SERVER_IP}"
        read -p "Press Enter when DNS is ready (or Ctrl+C to cancel)..."
    fi
    
    # SSL setup
    log_info "Setting up SSL certificates..."
    if [ ! -f "${BASE_DIR}/nginx/ssl/fullchain.pem" ]; then
        # Try to copy from existing stack
        if [ -f "/opt/xapi-ui-stack/nginx/ssl/fullchain.pem" ]; then
            log_info "Copying SSL from xapi-ui-stack..."
            cp /opt/xapi-ui-stack/nginx/ssl/fullchain.pem ${BASE_DIR}/nginx/ssl/
            cp /opt/xapi-ui-stack/nginx/ssl/privkey.pem ${BASE_DIR}/nginx/ssl/
        elif [ -f "/opt/lrs/ssl/fullchain.pem" ]; then
            log_info "Copying SSL from lrs stack..."
            cp /opt/lrs/ssl/fullchain.pem ${BASE_DIR}/nginx/ssl/
            cp /opt/lrs/ssl/privkey.pem ${BASE_DIR}/nginx/ssl/
        else
            # Try certbot
            log_info "Attempting to obtain Let's Encrypt certificate..."
            if command -v certbot &> /dev/null; then
                certbot certonly --standalone \
                    -d ${DOMAIN} \
                    --non-interactive \
                    --agree-tos \
                    -m ${EMAIL} && {
                    cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem ${BASE_DIR}/nginx/ssl/
                    cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem ${BASE_DIR}/nginx/ssl/
                    log_info "✓ SSL certificates obtained"
                } || {
                    log_error "Failed to obtain SSL certificates"
                    log_info "Please add certificates manually to: ${BASE_DIR}/nginx/ssl/"
                    exit 1
                }
            else
                log_error "certbot not found and no existing certificates"
                exit 1
            fi
        fi
        chmod 644 ${BASE_DIR}/nginx/ssl/*.pem
    else
        log_info "✓ SSL certificates already exist"
    fi
    
    log_info ""
    log_info "════════════════════════════════════════════════════"
    log_info "✓ Setup completed successfully!"
    log_info "════════════════════════════════════════════════════"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Build the application: ./deploy.sh build"
    log_info "  2. Start services: ./deploy.sh start"
    log_info "  3. Access at: https://${DOMAIN}"
    log_info ""
}

build() {
    log_step "Building ${PROJECT_NAME}..."
    cd ${BASE_DIR}
    
    log_info "Installing dependencies and building..."
    docker-compose build --no-cache
    
    log_info "✓ Build completed"
}

start() {
    log_step "Starting ${PROJECT_NAME}..."
    cd ${BASE_DIR}
    
    docker-compose up -d
    
    log_info "Waiting for services to be ready..."
    sleep 10
    
    status
}

stop() {
    log_step "Stopping ${PROJECT_NAME}..."
    cd ${BASE_DIR}
    docker-compose down
    log_info "✓ Services stopped"
}

restart() {
    log_step "Restarting ${PROJECT_NAME}..."
    stop
    sleep 3
    start
}

logs() {
    cd ${BASE_DIR}
    docker-compose logs -f --tail=100
}

status() {
    print_banner
    log_step "Checking service status..."
    
    # Container status
    echo ""
    log_info "Containers:"
    docker ps --filter "name=promptever-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || log_warn "No containers running"
    
    # Health checks
    echo ""
    log_info "Health Checks:"
    
    # App
    if curl -s http://localhost:9020/api/health > /dev/null 2>&1; then
        log_info "  ✓ App (9020) is healthy"
    else
        log_warn "  ✗ App (9020) is not responding"
    fi
    
    # Nginx
    if curl -s http://localhost:9021 > /dev/null 2>&1; then
        log_info "  ✓ Nginx (9021) is healthy"
    else
        log_warn "  ✗ Nginx (9021) is not responding"
    fi
    
    # HTTPS
    if curl -sk https://${DOMAIN}/api/health > /dev/null 2>&1; then
        log_info "  ✓ HTTPS (${DOMAIN}) is healthy"
    else
        log_warn "  ✗ HTTPS (${DOMAIN}) is not responding"
    fi
    
    # Backend (rag-api)
    if curl -s http://localhost:9009/health > /dev/null 2>&1; then
        log_info "  ✓ RAG API (9009) is healthy"
    else
        log_warn "  ✗ RAG API (9009) is not responding"
    fi
    
    # Resource usage
    echo ""
    log_info "Resource Usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
        promptever-app promptever-nginx 2>/dev/null || log_warn "Cannot get stats"
    
    echo ""
    log_info "════════════════════════════════════════════════════"
    log_info "Access: https://${DOMAIN}"
    log_info "════════════════════════════════════════════════════"
}

dev() {
    log_step "Starting development mode..."
    cd ${BASE_DIR}
    
    # Run with hot reload
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
}

# Main
case "${1}" in
    setup)
        setup
        ;;
    build)
        build
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    dev)
        dev
        ;;
    *)
        print_banner
        echo "Usage: $0 {command}"
        echo ""
        echo "Commands:"
        echo "  setup    - Initial setup (directories, SSL, DNS check)"
        echo "  build    - Build Docker images"
        echo "  start    - Start services"
        echo "  stop     - Stop services"
        echo "  restart  - Restart services"
        echo "  logs     - Show and follow logs"
        echo "  status   - Check service health"
        echo "  dev      - Start in development mode"
        echo ""
        echo "Quick Start:"
        echo "  1. ./deploy.sh setup"
        echo "  2. ./deploy.sh build"
        echo "  3. ./deploy.sh start"
        echo ""
        exit 1
        ;;
esac
