# Use a lightweight official Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# Install system dependencies needed for building packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (UID 1000) for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set working directory to the user's home app directory
WORKDIR $HOME/app

# Copy requirements file first to leverage Docker build cache
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy the rest of the application code
COPY --chown=user . .

# Ensure the data directory exists and is owned by the user
RUN mkdir -p $HOME/app/data

# Expose the port
EXPOSE 7860

# Start the server (using shell form so $PORT can be resolved dynamically if overridden)
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
