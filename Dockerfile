# Use the official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.38.0-focal

# Set environment variables to avoid prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for Flask
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app

# Expose the port your Flask app runs on
EXPOSE 4000

# Command to run your application
CMD ["python", "main.py"]
