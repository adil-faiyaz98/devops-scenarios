FROM python:3.9-slim

# Set working directory
WORKDIR /opt/program

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy model code
COPY models/ /opt/program/models/
COPY training/ /opt/program/training/
COPY inference/ /opt/program/inference/

# Set up environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/opt/program:${PATH}"

# Set up entry points
COPY docker/train /opt/program/train
COPY docker/serve /opt/program/serve
RUN chmod +x /opt/program/train /opt/program/serve

# Set up health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/ping || exit 1

# Default command
CMD ["serve"]
