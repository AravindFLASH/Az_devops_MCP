FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies (kept in sync with pyproject.toml).
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "mcp[cli]>=1.0.0,<2.0.0" \
    "azure-devops>=7.1.0b4" \
    "azure-identity>=1.17.0" \
    "msrest>=0.7.1" \
    "requests>=2.31.0" \
    "python-dotenv>=1.0.0" \
    "msal>=1.27.0"

# Copy only production files (local-only CLIs auth_utils.py/oauth_login.py excluded).
COPY ado_client.py auth.py mcp_app.py prompts.py resources.py server.py pyproject.toml ./
COPY tools ./tools

# Use a non-root user with a writable auth cache directory.
RUN useradd --create-home --shell /usr/sbin/nologin mcp && \
    mkdir -p /home/mcp/.claude/auth_cache && \
    chown -R mcp:mcp /app /home/mcp

USER mcp

# Mount .env at runtime via docker run -e or --env-file
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["python", "server.py"]
