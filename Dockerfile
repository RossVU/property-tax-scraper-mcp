FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application
COPY server.py .

# Expose port (if you add HTTP interface)
EXPOSE 8080

# Run MCP server
CMD ["python", "server.py"]
